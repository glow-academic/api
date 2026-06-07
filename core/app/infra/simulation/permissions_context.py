"""Simulation permissions context + shared save helpers.

Permissions context:
  1. resolve_simulation_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_simulation_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → simulations_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.cohort.search import search_cohorts
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.artifacts.simulation.get import (
    get_simulations as get_simulation_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.scenarios.search import search_scenarios
from app.tools.resources.simulations.create import (
    create_simulation as create_simulation_resource,
)

if TYPE_CHECKING:
    from app.infra.simulation.types import (
        CreateSimulationItem,
        SimulationFieldError,
        UpdateSimulationItem,
    )


@dataclass(frozen=True)
class SimulationPermissionsContext:
    """Lightweight context for simulation permission checks."""

    exists: bool
    department_ids: list[UUID]
    cohort_usage_count: int


async def resolve_simulation_permissions_context(
    conn: asyncpg.Connection,
    simulation_id: UUID,
) -> SimulationPermissionsContext:
    """Fetch just what's needed for simulation permission checks.

    Two black-box tool calls:
      1. get_simulation_artifacts → department_ids + simulation_ids (resource IDs)
      2. search_cohorts → any active cohorts using this simulation?
    """
    artifacts = await get_simulation_artifacts(
        conn,
        [simulation_id],
        departments=True,
        simulations=True,
    )

    if not artifacts:
        return SimulationPermissionsContext(
            exists=False,
            department_ids=[],
            cohort_usage_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])
    simulation_resource_ids = list(artifact.simulation_ids or [])

    _, total = (
        await search_cohorts(
            conn,
            simulation_ids=simulation_resource_ids,
            active_only=True,
            limit_count=1,
        )
        if simulation_resource_ids
        else ([], 0)
    )

    return SimulationPermissionsContext(
        exists=True,
        department_ids=department_ids,
        cohort_usage_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both simulation_create and simulation_update
# ---------------------------------------------------------------------------


async def resolve_simulation_values(
    pool: asyncpg.Pool,
    redis: Redis,
    item: CreateSimulationItem | UpdateSimulationItem,
    is_create: bool,
) -> list[SimulationFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments, scenarios, flags):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.simulation.types import SimulationFieldError

    errors: list[SimulationFieldError] = []

    async with pool.acquire() as conn:
        # --- Create resources ---

        if item.name is not None and item.name_id is None:
            result = await create_name(conn, item.name, redis)
            item.name_id = result.id

        if item.description is not None and item.description_id is None:
            result = await create_description(conn, item.description, redis)
            item.description_id = result.id

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
                        SimulationFieldError(
                            field="departments",
                            message=f'Department "{dept_name}" not found',
                        )
                    )
            if not any(e.field == "departments" for e in errors):
                item.department_ids = resolved_ids

        if item.scenarios is not None and item.scenario_ids is None:
            all_scenarios = await search_scenarios(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
            scenario_name_map = {
                s.name.lower(): s.id for s in all_scenarios if s.name and s.id
            }
            resolved_ids = []
            for scenario_name in item.scenarios:
                sid = scenario_name_map.get(scenario_name.lower())
                if sid:
                    resolved_ids.append(sid)
                else:
                    errors.append(
                        SimulationFieldError(
                            field="scenarios",
                            message=f'Scenario "{scenario_name}" not found',
                        )
                    )
            if not any(e.field == "scenarios" for e in errors):
                item.scenario_ids = resolved_ids

        # --- Scenario artifact ID → scenarios_resource ID resolution ---
        #
        # ``item.scenario_ids`` supplied directly by the client are
        # ``scenario_artifact`` IDs (that is what ``/scenario/search`` and the
        # simulation draft surface). The ``simulation_scenarios_junction``
        # constraint, however, references ``scenarios_resource(id)`` — the
        # denormalized snapshot row each scenario artifact owns via
        # ``scenario_scenarios_junction``. Writing the artifact ID straight
        # into the junction violates ``simulation_scenarios_scenario_id_fkey``
        # (HTTP 500). Resolve artifact IDs to their snapshot resource IDs here
        # so both the snapshot write and the junction write get resource IDs.
        #
        # Skip when ``item.scenarios`` was set: that branch already resolved
        # via the scenarios_resource search, yielding resource IDs.
        if item.scenarios is None and item.scenario_ids:
            scenario_artifacts = await get_scenarios(
                conn,
                list(item.scenario_ids),
                scenarios=True,
            )
            artifact_to_resource: dict[UUID, UUID] = {
                a.id: a.scenario_ids[0]
                for a in scenario_artifacts
                if a.id and a.scenario_ids
            }
            resolved_scenario_ids: list[UUID] = []
            for artifact_id in item.scenario_ids:
                resource_id = artifact_to_resource.get(artifact_id)
                if resource_id is not None:
                    resolved_scenario_ids.append(resource_id)
                elif artifact_id not in artifact_to_resource:
                    # Not a known scenario artifact. It may already be a
                    # resource ID (e.g. a re-submitted resolved value); leave
                    # it untouched so the junction FK still validates it.
                    resolved_scenario_ids.append(artifact_id)
            item.scenario_ids = resolved_scenario_ids

    # Resolve department *artifact* ids -> departments_resource ids before
    # the junction write. ``/department/search`` surfaces artifact ids, but
    # every ``*_departments_junction.departments_id`` is FK'd to
    # ``departments_resource``; writing a raw artifact id violates the FK
    # (HTTP 500). #282 class, missed for the cross-cutting ``department_ids``
    # dimension. Unknown/already-resolved ids pass through. No raw SQL.
    async with pool.acquire() as conn:
        item.department_ids = await resolve_department_ids_to_resource_ids(
            conn, getattr(item, "department_ids", None)
        )

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(
                SimulationFieldError(field="name", message="Name is required")
            )

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    practice: bool = False,
    department_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
) -> UUID:
    """Create a simulations_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        return await get_names(pool, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        return await get_descriptions(pool, [description_id], redis, bypass_cache=True
        )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_simulation_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            practice=practice,
            department_ids=department_ids,
            scenario_ids=scenario_ids,
            scenario_rubric_ids=scenario_rubric_ids,
            scenario_time_limit_ids=scenario_time_limit_ids,
            scenario_position_ids=scenario_position_ids,
            scenario_flag_ids=scenario_flag_ids,
        )
    return result.id
