"""Visibility helpers for dashboard analytics scopes."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from app.infra.profile_identity_context import ProfileIdentityContext


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
