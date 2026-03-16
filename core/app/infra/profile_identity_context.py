"""Resolve profile identity context from a profile artifact ID.

Given a profile_id (artifact), fetches the profile artifact's junctions,
hydrates resources in parallel, and returns a clean ProfileIdentityContext with
identity, role metadata, emails, departments, and settings.

Used by common_context to resolve the logged-in user's identity.
Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.roles.get import get_roles

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileIdentityContext:
    """Hydrated profile context for use by downstream infra layers."""

    profiles_id: UUID  # resource ID (from profile_profiles_junction)
    name: str
    role: str  # enum value: "superadmin", "admin", etc.
    role_name: str  # display name from roles_resource
    role_description: str
    role_artifacts: list[str]  # artifact types this role can access
    primary_email: str | None
    emails: list[str]  # all emails
    primary_department_id: UUID | None
    department_ids: list[UUID]  # all department IDs
    settings_id: UUID | None  # from primary department's setting_ids[0]
    requests_per_day: int | None  # rate limit from profiles_resource
    is_active: bool
    # Server-resolved session + group (set when session_id or group hints are provided)
    session_id: UUID | None = None
    group_id: UUID | None = None


# ---------------------------------------------------------------------------
# resolve_profile_identity_context
# ---------------------------------------------------------------------------


async def resolve_profile_identity_context(
    pool: asyncpg.Pool,
    profile_id: UUID,
    redis: Redis,
    bypass_cache: bool = False,
    # Server-resolved session (from require_auth middleware)
    session_id: UUID | None = None,
    # Group resolution hints (from request body — only needed for mutations)
    draft_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    artifact_type: str | None = None,
) -> ProfileIdentityContext | None:
    """Resolve a profile artifact ID into a hydrated ProfileIdentityContext.

    Each parallel branch acquires its own connection from the pool.

    Steps:
      1. get_profile_artifacts — fetches junction IDs
      2. asyncio.gather — hydrates all resources in parallel
      3. Pure Python assembly
      4. (Optional) resolve group_id from hints or create a fresh one
    """
    # Step 1: fetch profile artifact with all needed junctions
    async with pool.acquire() as conn:
        artifacts = await get_profile_artifacts(
            conn,
            [profile_id],
            active=None,
            names=True,
            roles=True,
            departments=True,
            emails=True,
            profiles=True,
            flags=True,
        )

    if not artifacts:
        return None

    artifact = artifacts[0]

    # Extract junction IDs
    name_ids = artifact.name_ids or []
    role_ids = artifact.role_ids or []
    department_ids = artifact.department_ids or []
    email_ids = artifact.email_ids or []
    profile_ids = artifact.profile_ids or []

    if not profile_ids:
        return None

    profiles_id = profile_ids[0]

    # Step 2: hydrate all resources in parallel

    async def _get_names() -> list:
        if not name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, name_ids, redis, bypass_cache)

    async def _get_roles() -> list:
        if not role_ids:
            return []
        async with pool.acquire() as conn:
            return await get_roles(conn, role_ids, redis, bypass_cache)

    async def _get_departments() -> list:
        if not department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, department_ids, redis, bypass_cache)

    async def _get_emails() -> list:
        if not email_ids:
            return []
        async with pool.acquire() as conn:
            return await get_emails(conn, email_ids, redis, bypass_cache)

    async def _get_profiles() -> list:
        async with pool.acquire() as conn:
            return await get_profiles(conn, profile_ids, redis, bypass_cache)

    (
        names_res,
        roles_res,
        depts_res,
        emails_res,
        profiles_res,
    ) = await asyncio.gather(
        _get_names(),
        _get_roles(),
        _get_departments(),
        _get_emails(),
        _get_profiles(),
    )

    # Step 3: extract values
    name = names_res[0].name if names_res else ""

    role = ""
    role_name = ""
    role_description = ""
    role_artifacts: list[str] = []
    if roles_res:
        r = roles_res[0]
        role = r.role
        role_name = r.name
        role_description = r.description
        role_artifacts = r.artifacts

    # Primary department: find the one with is_primary=True on the resource
    primary_department_id: UUID | None = None
    settings_id: UUID | None = None
    for dept in depts_res:
        if dept.is_primary:
            primary_department_id = dept.id
            if dept.setting_ids:
                settings_id = dept.setting_ids[0]
            break

    # Primary email: find the one with is_primary=True on the resource
    primary_email: str | None = None
    for email in emails_res:
        if email.is_primary:
            primary_email = email.email
            break

    all_emails = [e.email for e in emails_res]
    all_department_ids = [d.id for d in depts_res]

    # Rate limit from profiles_resource
    requests_per_day = profiles_res[0].requests_per_day if profiles_res else None

    # is_active: check if profile has an active "profile_active" flag
    # The artifact's active field reflects this
    is_active = artifact.active

    # Step 4: resolve group_id when mutation/generation context requires it
    resolved_group_id: UUID | None = None
    if draft_id or attempt_id or test_id or session_id:
        resolved_group_id = await _resolve_group_id(
            pool,
            profiles_id=profiles_id,
            session_id=session_id,
            draft_id=draft_id,
            attempt_id=attempt_id,
            test_id=test_id,
            artifact_type=artifact_type,
        )

    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name=name,
        role=role,
        role_name=role_name,
        role_description=role_description,
        role_artifacts=role_artifacts,
        primary_email=primary_email,
        emails=all_emails,
        primary_department_id=primary_department_id,
        department_ids=all_department_ids,
        settings_id=settings_id,
        requests_per_day=requests_per_day,
        is_active=is_active,
        session_id=session_id,
        group_id=resolved_group_id,
    )


# ---------------------------------------------------------------------------
# Group resolution (internal)
# ---------------------------------------------------------------------------


async def _resolve_group_id(
    pool: asyncpg.Pool,
    *,
    profiles_id: UUID,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    artifact_type: str | None = None,
) -> UUID | None:
    """Resolve a group_id from context hints, or create a fresh one.

    Priority:
      1. attempt_id → active chat → group_id
      2. test_id → latest invocation → group_id
      3. draft_id → draft's group_id
      4. otherwise create a fresh group for the provided session
    """
    from app.infra.identity.group import resolve_group

    async with pool.acquire() as conn:
        result = await resolve_group(
            conn,
            profiles_id=profiles_id,
            session_id=session_id,
            attempt_id=attempt_id,
            test_id=test_id,
            draft_id=draft_id,
            artifact_type=artifact_type,
        )

    if not result or not result.group_id:
        raise ValueError("Failed to resolve or create group_id for profile context")

    return UUID(result.group_id)
