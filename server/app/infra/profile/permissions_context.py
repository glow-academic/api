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
    from app.infra.profile.create import CreateProfileItem, ProfileFieldError
    from app.infra.profile.types import (
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
    from app.infra.profile.create import ProfileFieldError

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

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(ProfileFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    department_ids: list[UUID] | None = None,
) -> UUID:
    """Create a profiles_resource snapshot by hydrating IDs to values."""

    async def _empty() -> list:
        return []

    names = (
        await get_names(conn, [name_id], redis, bypass_cache=True)
        if name_id
        else await _empty()
    )

    result = await create_profile_resource(
        conn,
        redis,
        id=id,
        name=names[0].name if names else "",
        description="",
        department_ids=department_ids,
    )
    return result.id
