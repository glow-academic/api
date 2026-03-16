"""Simulation search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — scenario_ids -> scenarios_resource IDs, cohort_ids -> cohort artifacts
  3. search_simulations — core artifact search (IDs + total_count)
  4. get_simulations — hydrate junction IDs
  5. Resource get tools — hydrate scenarios, personas
  6. Permissions — compute per-simulation can_edit, can_delete, can_duplicate
  7. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.simulation.types import (
    ListSimulationApiPersona,
    ListSimulationApiResponse,
    ListSimulationApiScenario,
    ListSimulationApiSimulation,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.artifacts.simulation.search import search_simulations
from app.tools.resources.cohorts.search import (
    search_cohorts as search_cohorts_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.personas.get import (
    get_personas as get_personas_resource,
)
from app.tools.resources.scenarios.get import (
    get_scenarios as get_scenarios_resource,
)
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenarios_resource,
)

SIMULATION_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Clinical Assessment",
        "description": "The simulation's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "A clinical assessment simulation...",
        "description": "Optional description",
    },
    {
        "key": "is_inactive",
        "label": "Inactive",
        "type": "boolean",
        "example": "false",
        "description": "Whether the simulation is inactive (true/false)",
    },
    {
        "key": "is_practice",
        "label": "Practice",
        "type": "boolean",
        "example": "false",
        "description": "Whether the simulation is a practice simulation (true/false)",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
    {
        "key": "scenarios",
        "label": "Scenarios",
        "multi": True,
        "example": "Emergency Triage, Patient Intake",
        "description": "Comma-separated scenario names",
    },
]


async def search_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_scenario_ids: list[UUID] | None = None,
    filter_cohort_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    scenario_search: str | None = None,
    cohort_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    # Pagination
    page_size: int = 10,
    page_offset: int = 0,
) -> ListSimulationApiResponse:
    """Simulation search using composable infra functions."""
    from fastapi import HTTPException

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # -- Step 2: Reverse lookups --

    # filter_scenario_ids are scenarios_resource IDs — direct junction filter
    scenario_ids_filter = filter_scenario_ids

    # filter_cohort_ids are cohort_artifact IDs — search_simulations supports cohort_ids
    cohort_ids_filter = filter_cohort_ids

    # -- Step 3: Search simulations --
    async with pool.acquire() as conn:
        simulation_ids_result, total_count = await search_simulations(
            conn,
            search=search,
            department_ids=filter_department_ids,
            scenario_ids=scenario_ids_filter,
            cohort_ids=cohort_ids_filter,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not simulation_ids_result:
        return _empty_response(actor_name, total_count=0)

    # -- Step 4: Get simulation artifacts with junction IDs --
    async with pool.acquire() as conn:
        artifacts = await get_simulations(
            conn,
            simulation_ids_result,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            scenarios=True,
            simulations=True,
        )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_scenario_resource_ids: set[UUID] = set()

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        for sid in a.scenario_ids or []:
            all_scenario_resource_ids.add(sid)

    # Parallel: hydrate resources + facets

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_scenarios() -> list:
        if not all_scenario_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenarios_resource(
                conn, list(all_scenario_resource_ids), redis
            )

    async def _fetch_scenario_facet() -> list:
        async with pool.acquire() as conn:
            return await search_scenarios_resource(
                conn, redis, search=scenario_search, simulation=True, limit_count=100
            )

    async def _fetch_cohort_facet() -> list:
        async with pool.acquire() as conn:
            return await search_cohorts_resource(
                conn, redis, search=cohort_search, cohort=True, limit_count=100
            )

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, simulation=True, limit_count=100
            )

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, simulation=True, limit_count=100
            )

    (
        names_data,
        scenarios_data,
        scenario_facet,
        cohort_facet,
        department_facet,
        flag_facet,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_scenarios(),
        _fetch_scenario_facet(),
        _fetch_cohort_facet(),
        _fetch_department_facet(),
        _fetch_flag_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}

    # Collect persona IDs from scenarios for color dot rendering
    all_persona_ids: set[UUID] = set()
    for s in scenarios_data:
        for pid in s.persona_ids or []:
            all_persona_ids.add(pid)

    # Fetch personas for color mapping
    personas_data = []
    if all_persona_ids:
        async with pool.acquire() as conn:
            personas_data = await get_personas_resource(
                conn, list(all_persona_ids), redis
            )

    persona_map: dict[UUID, str] = {
        p.persona_id: p.color or "" for p in personas_data if p.persona_id
    }

    # Build scenario mapping with persona colors
    scenario_mapping: list[ListSimulationApiScenario] = []
    for s in scenarios_data:
        p_ids = s.persona_ids or []
        scenario_mapping.append(
            ListSimulationApiScenario(
                scenario_id=s.id,
                name=s.name,
                persona_ids=[str(pid) for pid in p_ids],
                persona_mapping=[
                    ListSimulationApiPersona(
                        persona_id=str(pid),
                        color=persona_map.get(pid, ""),
                    )
                    for pid in p_ids
                    if pid in persona_map
                ],
            )
        )

    # Count cohorts per simulation via simulations_resource junction
    # We approximate by using the cohort facet data
    # For now, count cohort links via the simulations_resource IDs
    cohort_count_map: dict[UUID, int] = {}
    for a in artifacts:
        sim_resource_ids = set(a.simulation_ids or [])
        count = sum(
            1 for c in cohort_facet if sim_resource_ids & set(c.simulation_ids or [])
        )
        cohort_count_map[a.id] = count

    # -- Step 6: Build simulation list with permissions --
    api_simulations: list[ListSimulationApiSimulation] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        cohort_usage = cohort_count_map.get(a.id, 0)

        can_edit_val = compute_can_edit(
            user_role=user_role,
            simulation_department_ids=dept_ids_str,
            cohort_usage_count=cohort_usage,
            user_department_ids=user_department_ids,
        )
        can_delete_val = compute_can_delete(
            user_role=user_role,
            simulation_department_ids=dept_ids_str,
            cohort_usage_count=cohort_usage,
        )
        can_duplicate_val = compute_can_duplicate(user_role)

        # Determine practice flag from flags junction
        is_inactive = not a.active

        api_simulations.append(
            ListSimulationApiSimulation(
                simulation_id=a.id,
                name=name_obj.name if name_obj else None,
                description=None,
                department_ids=dept_ids_str,
                is_inactive=is_inactive,
                practice_simulation=None,
                generated=a.generated,
                mcp=a.mcp,
                scenario_ids=[str(sid) for sid in (a.scenario_ids or [])],
                num_cohorts=cohort_usage,
                cohort_usage_count=cohort_usage,
                can_edit=can_edit_val,
                can_delete=can_delete_val,
                can_duplicate=can_duplicate_val,
                cohort_ids=None,
                updated_at=a.updated_at,
            )
        )

    # -- Step 7: Build facet sections --
    scenario_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0) for s in scenario_facet
        ],
        selected_ids=[str(sid) for sid in filter_scenario_ids]
        if filter_scenario_ids
        else None,
        search=scenario_search,
    )

    cohort_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(c.id), name=c.name, count=0) for c in cohort_facet
        ],
        selected_ids=[str(cid) for cid in filter_cohort_ids]
        if filter_cohort_ids
        else None,
        search=cohort_search,
    )

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in filter_department_ids]
        if filter_department_ids
        else None,
        search=department_search,
    )

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListSimulationApiResponse(
        actor_name=actor_name,
        simulations=api_simulations,
        scenarios=scenario_mapping,
        scenario_filter=scenario_filter,
        cohort_filter=cohort_filter,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListSimulationApiResponse:
    return ListSimulationApiResponse(
        actor_name=actor_name,
        simulations=[],
        scenarios=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
