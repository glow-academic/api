"""Profile permissions context + shared save helpers.

Permissions context:
  1. resolve_profile_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_profile_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → profiles_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.cohort.search import search_cohorts
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.create import (
    create_profile as create_profile_resource,
)

if TYPE_CHECKING:
    from app.infra.profile.types import (
        CreateProfileItem,
        ProfileFieldError,
        UpdateProfileItem,
    )


@dataclass(frozen=True)
class ProfilePermissionsContext:
    """Lightweight context for profile permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_cohort_count: int


async def resolve_profile_permissions_context(
    conn: asyncpg.Connection,
    target_profile_id: UUID,
) -> ProfilePermissionsContext:
    """Fetch just what's needed for profile permission checks.

    Two black-box tool calls:
      1. get_profile_artifacts → department_ids + profile_ids (resource IDs)
      2. search_cohorts → any active cohorts using this profile?
    """
    artifacts = await get_profile_artifacts(
        conn,
        [target_profile_id],
        departments=True,
        profiles=True,
    )

    if not artifacts:
        return ProfilePermissionsContext(
            exists=False,
            department_ids=[],
            active_cohort_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])
    profile_resource_ids = list(artifact.profile_ids or [])

    # TODO: Refine — currently checks if any active cohort references this
    # profile. Eventually should check if this is the *last* profile in
    # the cohort before blocking removal.
    _, total = (
        await search_cohorts(
            conn,
            profile_ids=profile_resource_ids,
            active_only=True,
            limit_count=1,
        )
        if profile_resource_ids
        else ([], 0)
    )

    return ProfilePermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_cohort_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both profile_create and profile_update
# ---------------------------------------------------------------------------


async def resolve_profile_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateProfileItem | UpdateProfileItem,
    is_create: bool,
) -> list[ProfileFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name):
      Creates a new resource via the create tool.
    For 'match' resources (departments):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.profile.types import ProfileFieldError

    errors: list[ProfileFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    # --- Match resources ---

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    ProfileFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # Resolve department *artifact* ids -> departments_resource ids before
    # the junction write. ``/department/search`` surfaces artifact ids, but
    # every ``*_departments_junction.departments_id`` is FK'd to
    # ``departments_resource``; writing a raw artifact id violates the FK
    # (HTTP 500). #282 class, missed for the cross-cutting ``department_ids``
    # dimension. Unknown/already-resolved ids pass through. No raw SQL.
    item.department_ids = await resolve_department_ids_to_resource_ids(
        conn, getattr(item, "department_ids", None)
    )

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(ProfileFieldError(field="name", message="Name is required"))

    return errors


async def assert_role_assignable(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    role_id: UUID | None,
    actor_role_level: int,
) -> None:
    """Reject assigning a role whose privilege level outranks the actor.

    The body-supplied ``role_id`` on profile create/update sets the
    profile's role — a privilege-bearing attribute. The read surface
    (``profile/get.py`` via ``compute_role_options``) only offers roles at
    or below the actor's level (``role.level >= actor.role_level``; higher
    number = lower privilege), but the write path historically trusted the
    request value directly. This mirrors that gate server-side so a
    lower-privileged actor cannot mass-assign a higher-privilege role
    (e.g. level-0 admin) to a profile.

    Level-0 actors (top privilege) may assign any role. A ``role_id`` that
    doesn't resolve, or a role with no level, is rejected as un-assignable
    rather than silently allowed.
    """
    if role_id is None:
        return
    if actor_role_level == 0:
        return

    from fastapi import HTTPException

    from app.tools.resources.roles.get import get_roles

    roles = await get_roles(conn, [role_id], redis)
    target_level = roles[0].level if roles else None
    if target_level is None or target_level < actor_role_level:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to assign this role.",
        )


async def create_denormalized_snapshot(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    department_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    role_id: UUID | None = None,
) -> UUID:
    """Create a profiles_resource snapshot by hydrating IDs to values."""
    from app.tools.resources.emails.get import get_emails

    names = (
        await get_names(conn, [name_id], redis, bypass_cache=True)
        if name_id
        else []
    )

    # Resolve email IDs to strings for denormalized snapshot
    emails: list[str] = []
    primary_email: str | None = None
    if email_ids:
        email_objs = await get_emails(conn, email_ids, redis, bypass_cache=True)
        for e in email_objs:
            if e.email:
                emails.append(e.email)
                if not primary_email:
                    primary_email = e.email

    result = await create_profile_resource(
        conn,
        redis,
        id=id,
        name=names[0].name if names else "",
        description="",
        department_ids=department_ids,
        role_id=role_id,
        emails=emails if emails else None,
        primary_email=primary_email,
    )
    return result.id
