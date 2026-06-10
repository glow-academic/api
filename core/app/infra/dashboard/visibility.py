"""Visibility helpers for dashboard analytics scopes."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import asyncpg

from app.infra.profile_identity_context import ProfileIdentityContext


def department_scope_allows(
    *,
    caller_role_level: int,
    caller_department_ids: Sequence[UUID],
    owner_role_level: int | None,
    owner_department_ids: Sequence[UUID],
) -> bool:
    """Pure department-overlap predicate shared across visibility boundaries.

    This is the canonical dept-scope rule that ``resolve_visible_profile_ids``
    (dashboard, #152) and ``leaderboard/export`` enforce on bulk reads, lifted
    into a single reusable unit so the per-resource gates (attempt read/media,
    emulation) draw the SAME boundary instead of reinventing one.

    A caller may reach an owner/target profile when:

    - ``caller_role_level == 0`` — SUPER-ADMIN sees everything (global).
    - ``owner_role_level is None`` — a ROLELESS profile is shared/system
      identity, not a department-scoped student; never hidden.
    - ``owner_department_ids`` is empty — a GLOBAL profile (no department
      restriction) is visible to everyone, mirroring the
      ``department_ids = '{}'`` inclusion in ``resolve_visible_simulation_scope``.
    - otherwise the owner/target must SHARE at least one department with the
      caller (``owner_department_ids && caller_department_ids`` overlap).

    SELF-access is intentionally NOT handled here — callers short-circuit self
    (and it is allowed irrespective of department).
    """
    if caller_role_level == 0:
        return True
    if owner_role_level is None:
        return True
    if not owner_department_ids:
        return True
    return bool(set(caller_department_ids) & set(owner_department_ids))


async def is_profile_in_department_scope(
    pool: asyncpg.Pool,
    caller: ProfileIdentityContext,
    owner_profiles_id: UUID,
) -> bool:
    """Whether ``owner_profiles_id`` falls within ``caller``'s department scope.

    Single-profile sibling of ``resolve_visible_profile_ids``: it resolves the
    owner profile's role level + ``department_ids`` from ``profiles_resource``
    (the same columns/source the bulk scope reads) and applies the shared
    :func:`department_scope_allows` predicate. Used by the per-attempt
    read/media gate so a non-super caller can only reach attempts owned by a
    profile that shares one of their departments (or is global/roleless),
    matching the dashboard/leaderboard boundary (#152/#148).

    A missing owner row fails closed (returns ``False``).
    """
    if caller.role_level == 0:
        return True
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.department_ids AS department_ids, r.level AS role_level
            FROM profiles_resource p
            LEFT JOIN roles_resource r
              ON r.id = p.role_id
             AND r.active = true
            WHERE p.id = $1
            """,
            owner_profiles_id,
        )
    if row is None:
        return False
    return department_scope_allows(
        caller_role_level=caller.role_level,
        caller_department_ids=caller.department_ids,
        owner_role_level=row["role_level"],
        owner_department_ids=row["department_ids"] or [],
    )


async def resolve_visible_profile_ids(
    pool: asyncpg.Pool,
    profile: ProfileIdentityContext,
) -> list[UUID]:
    """Return profile-resource IDs visible to the actor for org analytics."""
    if profile.role_level == 0:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id
                FROM profiles_resource
                WHERE active = true
                ORDER BY name NULLS LAST, id
                """
            )
        return [row["id"] for row in rows]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id
            FROM profiles_resource p
            LEFT JOIN roles_resource r
              ON r.id = p.role_id
             AND r.active = true
            WHERE p.active = true
              AND (
                    p.id = $1
                 OR (
                    p.department_ids && $2::uuid[]
                    AND (r.id IS NULL OR r.level >= $3)
                 )
              )
            ORDER BY p.name NULLS LAST, p.id
            """,
            profile.profiles_id,
            list(profile.department_ids or []),
            profile.role_level,
        )
    return [row["id"] for row in rows]


async def resolve_visible_simulation_scope(
    pool: asyncpg.Pool,
    profile: ProfileIdentityContext,
    *,
    department_ids: list[UUID] | None = None,
) -> tuple[list[UUID], list[UUID]]:
    """Return visible simulation-resource IDs and their scenario IDs."""
    params: list[object] = []
    conditions = ["active = true"]

    if profile.role_level > 0:
        params.append(list(profile.department_ids or []))
        conditions.append(
            "(department_ids = '{}'::uuid[] OR department_ids && $1::uuid[])"
        )

    if department_ids:
        params.append(department_ids)
        conditions.append(f"department_ids && ${len(params)}::uuid[]")

    where_sql = " AND ".join(conditions)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, scenario_ids
            FROM simulations_resource
            WHERE {where_sql}
            ORDER BY name, id
            """,
            *params,
        )

    simulation_ids = [row["id"] for row in rows]
    scenario_ids: list[UUID] = []
    seen: set[UUID] = set()
    for row in rows:
        for scenario_id in row["scenario_ids"] or []:
            if scenario_id in seen:
                continue
            seen.add(scenario_id)
            scenario_ids.append(scenario_id)

    return simulation_ids, scenario_ids
