"""Resolve profile upsert — composes canonical black boxes.

Given profile data (name, emails, role, departments):
  1. Validate role hierarchy via resolve_profile_identity_context + SIMULATABLE_ROLES
  2. Resolve resources: create_name, create_email, search_roles, search_flags
  3. Find existing profile by primary email: search_profiles(email_ids=...)
  4. Create or update profile artifact + denormalized snapshot
  5. Create session (append-only)

No inline SQL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile.permissions_context import create_denormalized_snapshot
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.artifacts.profile.search import search_profiles
from app.tools.artifacts.profile.update import (
    update_profile as update_profile_artifact,
)
from app.tools.entries.sessions.create import create_session
from app.tools.resources.emails.create import create_email
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.roles.search import search_roles

ResolveProfileIdentityFn = Callable[..., Awaitable[object | None]]
CreateNameFn = Callable[..., Awaitable[object]]
CreateEmailFn = Callable[..., Awaitable[object]]
SearchRolesFn = Callable[..., Awaitable[list[object]]]
SearchFlagsFn = Callable[..., Awaitable[list[object]]]
SearchProfilesFn = Callable[..., Awaitable[tuple[list[UUID], int]]]
CreateSnapshotFn = Callable[..., Awaitable[UUID]]
CreateProfileArtifactFn = Callable[..., Awaitable[object]]
UpdateProfileArtifactFn = Callable[..., Awaitable[object]]
CreateSessionFn = Callable[..., Awaitable[object]]


@dataclass(frozen=True)
class UpsertProfileResult:
    """Result of a profile upsert."""

    profile_id: UUID
    created: bool
    session_id: UUID


async def resolve_profile_upsert(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    name: str,
    emails: list[str],
    role: str,
    primary_email_index: int = 0,
    active: bool = True,
    department_ids: list[UUID] | None = None,
    profile_id_new: UUID | None = None,
    current_profile_id: UUID | None = None,
    bypass_cache: bool = False,
    resolve_profile_identity_fn: ResolveProfileIdentityFn | None = None,
    create_name_fn: CreateNameFn | None = None,
    create_email_fn: CreateEmailFn | None = None,
    search_roles_fn: SearchRolesFn | None = None,
    search_flags_fn: SearchFlagsFn | None = None,
    search_profiles_fn: SearchProfilesFn | None = None,
    create_snapshot_fn: CreateSnapshotFn | None = None,
    create_profile_artifact_fn: CreateProfileArtifactFn | None = None,
    update_profile_artifact_fn: UpdateProfileArtifactFn | None = None,
    create_session_fn: CreateSessionFn | None = None,
) -> UpsertProfileResult:
    """Create or update a profile by primary email.

    Composes canonical black boxes — no inline SQL.
    """
    resolve_profile_identity_fn = (
        resolve_profile_identity_fn or resolve_profile_identity_context
    )
    create_name_fn = create_name_fn or create_name
    create_email_fn = create_email_fn or create_email
    search_roles_fn = search_roles_fn or search_roles
    search_flags_fn = search_flags_fn or search_flags
    search_profiles_fn = search_profiles_fn or search_profiles
    create_snapshot_fn = create_snapshot_fn or create_denormalized_snapshot
    create_profile_artifact_fn = create_profile_artifact_fn or create_profile_artifact
    update_profile_artifact_fn = update_profile_artifact_fn or update_profile_artifact
    create_session_fn = create_session_fn or create_session

    # ── Step 1: Role hierarchy validation ───────────────────────────────
    if current_profile_id:
        requester = await resolve_profile_identity_fn(
            pool, current_profile_id, redis, bypass_cache=bypass_cache
        )
        if requester:
            allowed_roles = SIMULATABLE_ROLES.get(requester.role, set())
            if role not in allowed_roles:
                raise ValueError(f"Role '{requester.role}' cannot assign role '{role}'")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # ── Step 2: Resolve resources ───────────────────────────────────────
            # Name
            name_resource = await create_name_fn(conn, name, redis)
            name_id = name_resource.id

            # Emails
            email_ids: list[UUID] = []
            for email in emails:
                email_resource = await create_email_fn(conn, email, redis)
                email_ids.append(email_resource.id)

            primary_email_id = email_ids[primary_email_index] if email_ids else None

            # Role
            role_items = await search_roles_fn(
                conn, redis, search=role, limit_count=10, bypass_cache=bypass_cache
            )
            role_id: UUID | None = None
            for r in role_items:
                if r.role == role:
                    role_id = r.id
                    break
            if not role_id:
                raise ValueError(f"Role '{role}' not found")

            # Flag (profile_active)
            flag_items = await search_flags_fn(
                conn,
                redis,
                search="profile_active",
                limit_count=10,
                bypass_cache=bypass_cache,
            )
            flag_id: UUID | None = None
            for f in flag_items:
                if f.name == "profile_active":
                    flag_id = f.id
                    break

            # ── Step 3: Find existing profile by primary email ──────────────────
            existing_ids: list[UUID] = []
            if primary_email_id:
                existing_ids, _ = await search_profiles_fn(
                    conn,
                    email_ids=[primary_email_id],
                    active_only=False,
                    limit_count=1,
                )

            created = len(existing_ids) == 0

            # ── Step 4: Create or update profile artifact ───────────────────────
            flag_ids = [flag_id] if flag_id and active else None

            if created:
                # Create denormalized profiles_resource snapshot
                profiles_resource_id = await create_snapshot_fn(
                    conn, redis, id=profile_id_new, name_id=name_id
                )

                result = await create_profile_artifact_fn(
                    conn,
                    id=profile_id_new,
                    name_id=name_id,
                    email_ids=email_ids,
                    role_ids=[role_id],
                    department_ids=department_ids,
                    flag_ids=flag_ids,
                    profile_ids=[profiles_resource_id],
                    redis=redis,
                )
                profile_id = result.id
            else:
                profile_id = existing_ids[0]

                # Create denormalized profiles_resource snapshot
                profiles_resource_id = await create_snapshot_fn(
                    conn, redis, name_id=name_id
                )

                await update_profile_artifact_fn(
                    conn,
                    profile_id,
                    name_id=name_id,
                    email_ids=email_ids,
                    role_ids=[role_id],
                    department_ids=department_ids,
                    flag_ids=flag_ids,
                    profile_ids=[profiles_resource_id],
                    redis=redis,
                )

            # ── Step 5: Create session (append-only) ────────────────────────────
            session = await create_session_fn(conn, profiles_resource_id)

    return UpsertProfileResult(
        profile_id=profile_id,
        created=created,
        session_id=session.id,
    )
