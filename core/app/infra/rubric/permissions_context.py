"""Rubric permissions context + shared save helpers.

Permissions context:
  1. resolve_rubric_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_rubric_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → rubrics_resource snapshot

Composes existing black-box fetchers — no raw SQL where possible.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.rubric.get import (
    get_rubrics as get_rubric_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.rubrics.create import (
    create_rubric as create_rubric_resource,
)

if TYPE_CHECKING:
    from app.infra.rubric.create import CreateRubricItem, RubricFieldError
    from app.infra.rubric.types import (
        UpdateRubricItem,
    )


@dataclass(frozen=True)
class RubricPermissionsContext:
    """Lightweight context for rubric permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_simulation_count: int


async def resolve_rubric_permissions_context(
    conn: asyncpg.Connection,
    rubric_id: UUID,
) -> RubricPermissionsContext:
    """Fetch just what's needed for rubric permission checks.

    Two calls:
      1. get_rubric_artifacts → department_ids
      2. SQL count → active simulations using this rubric
    """
    artifacts = await get_rubric_artifacts(
        conn,
        [rubric_id],
        departments=True,
    )

    if not artifacts:
        return RubricPermissionsContext(
            exists=False,
            department_ids=[],
            active_simulation_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    # Count active simulations using this rubric via scenario_rubrics_resource.
    # This replicates the SQL from get_rubric_access_complete.sql.
    row = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT ss.simulation_id)::int
        FROM simulation_scenarios_junction ss
        JOIN simulation_scenario_rubrics_junction ssr
            ON ssr.simulation_id = ss.simulation_id
        JOIN scenario_rubrics_resource srr
            ON srr.id = ssr.scenario_rubrics_id
            AND srr.scenario_id = ss.scenarios_id
        WHERE srr.rubric_id = $1
          AND EXISTS (
              SELECT 1 FROM simulation_scenario_flags_junction ssf
              JOIN scenario_flags_resource sfr ON ssf.scenario_flags_id = sfr.id
              JOIN flags_resource f ON sfr.flag_id = f.id
              WHERE ssf.simulation_id = ss.simulation_id
                AND sfr.scenario_id = ss.scenarios_id
                AND f.type = 'scenario_active'
                AND f.value = true
          )
        """,
        rubric_id,
    )

    return RubricPermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_simulation_count=row or 0,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both rubric_create and rubric_update
# ---------------------------------------------------------------------------


async def resolve_rubric_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateRubricItem | UpdateRubricItem,
    is_create: bool,
) -> list[RubricFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments, active_flag):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.rubric.create import RubricFieldError

    errors: list[RubricFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Match resources ---

    if item.active_flag is not None and item.active_flag_id is None:
        results = await search_flags(
            conn,
            redis,
            search=None,
            flag_type="rubric_active",
            limit_count=100,
        )
        match = next((r for r in results if r.type == "rubric_active"), None)
        if match and match.id:
            if item.active_flag:
                item.active_flag_id = match.id
        elif item.active_flag:
            errors.append(
                RubricFieldError(
                    field="active_flag", message="Active flag resource not found"
                )
            )

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids: list[UUID] = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    RubricFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(RubricFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
) -> UUID:
    """Create a rubrics_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_rubric_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            standard_group_ids=standard_group_ids,
        )
    return result.id
