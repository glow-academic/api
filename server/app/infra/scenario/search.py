"""Scenario search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — simulation_ids → scenarios_resource IDs, persona_ids → direct junction
  3. search_scenarios — core artifact search (IDs + total_count)
  4. get_scenarios — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions, etc.
  6. Permissions — compute per-scenario can_edit, can_delete, can_duplicate
  7. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.persona.types import ImportField
from app.infra.scenario.types import (
    ListScenarioApiCohort,
    ListScenarioApiDepartment,
    ListScenarioApiField,
    ListScenarioApiObjective,
    ListScenarioApiPersona,
    ListScenarioApiResponse,
    ListScenarioApiScenario,
    ListScenarioApiSimulation,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import (
    search_departments,
)
from app.tools.resources.fields.get import get_fields
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.personas.get import (
    get_personas as get_personas_resource,
)
from app.tools.resources.personas.search import (
    search_personas as search_personas_resource,
)
from app.tools.resources.scenarios.get import (
    get_scenarios as get_scenarios_resource,
)
from app.tools.resources.simulations.get import (
    get_simulations as get_simulations_resource,
)
from app.tools.resources.simulations.search import (
    search_simulations as search_simulations_resource,
)

SCENARIO_IMPORT_FIELDS: list[ImportField] = [
    ImportField(
        key="name",
        label="Name",
        required=True,
        example="Emergency Triage",
        description="The scenario's display name",
    ),
    ImportField(
        key="description",
        label="Description",
        example="A triage scenario...",
        description="Optional description",
    ),
    ImportField(
        key="problem_statement",
        label="Problem Statement",
        example="A patient arrives...",
        description="The scenario problem statement",
    ),
    ImportField(
        key="active_flag",
        label="Active",
        type="boolean",
        example="true",
        description="Whether the scenario is active (true/false)",
    ),
    ImportField(
        key="departments",
        label="Departments",
        multi=True,
        example="Nursing, Medicine",
        description="Comma-separated department names",
    ),
    ImportField(
        key="personas",
        label="Personas",
        multi=True,
        example="Sarah the Nurse",
        description="Comma-separated persona names",
    ),
    ImportField(
        key="documents",
        label="Documents",
        multi=True,
        example="Protocol Guide",
        description="Comma-separated document names",
    ),
    ImportField(
        key="parameter_fields",
        label="Parameter Fields",
        multi=True,
        example="Patient Age, Condition",
        description="Comma-separated parameter field names",
    ),
    ImportField(
        key="objectives",
        label="Objectives",
        multi=True,
        example="Assess patient",
        description="Comma-separated objective texts",
    ),
    ImportField(
        key="images",
        label="Images",
        multi=True,
        example="X-Ray Image",
        description="Comma-separated image names",
    ),
    ImportField(
        key="videos",
        label="Videos",
        multi=True,
        example="Training Video",
        description="Comma-separated video names",
    ),
    ImportField(
        key="questions",
        label="Questions",
        multi=True,
        example="What is the diagnosis?",
        description="Comma-separated question texts",
    ),
    ImportField(
        key="options",
        label="Options",
        multi=True,
        example="Option A, Option B",
        description="Comma-separated option texts",
    ),
]


async def search_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    persona_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    persona_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    # Pagination
    page_size: int = 10,
    page_offset: int = 0,
) -> ListScenarioApiResponse:
    """Scenario search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, departments, name
      2. Reverse lookups (simulation_ids -> scenarios_resource IDs)
      3. search_scenarios -> (scenario_artifact_ids, total_count)
      4. get_scenarios -> hydrate junction IDs
      5. Parallel: hydrate resources + compute permissions + facets
    """
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

    # simulation_ids -> scenarios_resource IDs via simulation's scenarios junction
    scenario_resource_ids: list[UUID] | None = None

    async with pool.acquire() as conn:
        if simulation_ids:
            # search_simulations_resource returns simulation resources with scenario_ids
            sims = await get_simulations_resource(conn, simulation_ids, redis)
            sids: set[UUID] = set()
            for s in sims:
                sids.update(s.scenario_ids or [])
            if sids:
                scenario_resource_ids = list(sids)
            else:
                return _empty_response(actor_name)

        # persona_ids are personas_resource IDs — direct junction filter on scenario
        # search_scenarios supports persona_ids directly

        # -- Step 3: Search scenarios --
        scenario_ids_result, total_count = await search_scenarios(
            conn,
            search=search,
            department_ids=filter_department_ids,
            persona_ids=persona_ids,
            scenario_ids=scenario_resource_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

        if not scenario_ids_result:
            return _empty_response(actor_name, total_count=0)

        # -- Step 4: Get scenario artifacts with junction IDs --
        artifacts = await get_scenarios(
            conn,
            scenario_ids_result,
            names=True,
            descriptions=True,
            departments=True,
            objectives=True,
            personas=True,
            parameter_fields=True,
            scenarios=True,
        )

    # -- Step 5: Parallel hydration + facets --

    # Collect all resource IDs to hydrate
    all_name_ids: list[UUID] = []
    all_persona_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()
    all_objective_ids: set[UUID] = set()
    all_field_ids: set[UUID] = set()
    all_scenario_resource_ids: set[UUID] = set()

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        for pid in a.persona_ids or []:
            all_persona_ids.add(pid)
        for did in a.department_ids or []:
            all_department_ids.add(did)
        for oid in a.objective_ids or []:
            all_objective_ids.add(oid)
        for fid in a.parameter_field_ids or []:
            all_field_ids.add(fid)
        for sid in a.scenario_ids or []:
            all_scenario_resource_ids.add(sid)

    # Parallel: hydrate resources + facets
    # Each branch acquires its own connection from the pool.

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_personas() -> list:
        if not all_persona_ids:
            return []
        async with pool.acquire() as conn:
            return await get_personas_resource(conn, list(all_persona_ids), redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, list(all_department_ids), redis)

    async def _get_objectives() -> list:
        if not all_objective_ids:
            return []
        async with pool.acquire() as conn:
            return await get_objectives(conn, list(all_objective_ids), redis)

    async def _get_fields() -> list:
        if not all_field_ids:
            return []
        async with pool.acquire() as conn:
            return await get_fields(conn, list(all_field_ids), redis)

    async def _get_scenarios_resource() -> list:
        if not all_scenario_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenarios_resource(
                conn, list(all_scenario_resource_ids), redis
            )

    async def _get_persona_facet() -> list:
        async with pool.acquire() as conn:
            return await search_personas_resource(
                conn, redis, search=persona_search, scenario=True, limit_count=100
            )

    async def _get_simulation_facet() -> list:
        async with pool.acquire() as conn:
            return await search_simulations_resource(
                conn, redis, search=simulation_search, simulation=True, limit_count=100
            )

    async def _get_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, scenario=True, limit_count=100
            )

    async def _get_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, scenario=True, limit_count=100
            )

    (
        names_data,
        personas_data,
        departments_data,
        objectives_data,
        fields_data,
        scenarios_resource_data,
        persona_facet,
        simulation_facet,
        department_facet,
        flag_facet,
    ) = await asyncio.gather(
        _get_names(),
        _get_personas(),
        _get_departments(),
        _get_objectives(),
        _get_fields(),
        _get_scenarios_resource(),
        _get_persona_facet(),
        _get_simulation_facet(),
        _get_department_facet(),
        _get_flag_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}

    # Count active simulations per scenario via scenarios_resource_data
    # For each scenario artifact, we need to count how many simulations reference its scenarios_resource IDs
    sim_count_map: dict[UUID, int] = {}
    for a in artifacts:
        count = 0
        for sr in scenarios_resource_data:
            if sr.id in set(a.scenario_ids or []):
                # This scenarios_resource is linked to this scenario
                # Count simulations from facet data
                count += len(
                    [
                        sf
                        for sf in simulation_facet
                        if sr.id and sr.id in set(sf.scenario_ids or [])
                    ]
                )
        sim_count_map[a.id] = count

    # Build mapping arrays for the response
    api_objectives: list[ListScenarioApiObjective] = [
        ListScenarioApiObjective(
            objective_id=str(getattr(o, "objective_id", None) or o.id)
            if (getattr(o, "objective_id", None) or getattr(o, "id", None))
            else None,
            name=getattr(o, "objective", None) or "",
            description=getattr(o, "objective", None) or "",
        )
        for o in objectives_data
    ]

    api_fields: list[ListScenarioApiField] = [
        ListScenarioApiField(
            field_id=str(getattr(f, "field_id", None) or f.id)
            if (getattr(f, "field_id", None) or getattr(f, "id", None))
            else None,
            name=f.name,
            description=f.description or "",
        )
        for f in fields_data
    ]

    # Cohorts: collect from scenarios_resource data
    all_cohort_ids: set[UUID] = set()
    # We don't have cohort IDs on scenarios directly, fetch separately if needed
    # For now, the cohort mapping was in the old SQL but not core - pass empty
    api_cohorts: list[ListScenarioApiCohort] = []

    api_personas: list[ListScenarioApiPersona] = [
        ListScenarioApiPersona(
            persona_id=str(getattr(p, "persona_id", None) or p.id)
            if (getattr(p, "persona_id", None) or getattr(p, "id", None))
            else None,
            name=p.name or "",
            description=p.description or "",
            color=getattr(p, "color", None) or "",
            icon=getattr(p, "icon", None) or "",
        )
        for p in personas_data
    ]

    api_simulations: list[ListScenarioApiSimulation] = [
        ListScenarioApiSimulation(
            simulation_id=str(s.id) if s.id else None,
            name=getattr(s, "name", None) or "",
            description=s.description or "",
            department_ids=getattr(s, "department_ids", None),
        )
        for s in simulation_facet
    ]

    api_departments: list[ListScenarioApiDepartment] = [
        ListScenarioApiDepartment(
            department_id=str(getattr(d, "department_id", None) or d.id)
            if (getattr(d, "department_id", None) or getattr(d, "id", None))
            else None,
            name=d.name or "",
            description=d.description or "",
        )
        for d in departments_data
    ]

    # -- Step 6: Build scenario list with permissions --
    api_scenarios: list[ListScenarioApiScenario] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        # Count simulations for this scenario
        num_simulations = sim_count_map.get(a.id, 0)

        can_edit_val = compute_can_edit(
            user_role=user_role,
            scenario_department_ids=dept_ids_str,
            active_simulation_count=num_simulations,
            user_department_ids=user_department_ids,
        )
        can_delete_val = compute_can_delete(
            user_role=user_role,
            scenario_department_ids=dept_ids_str,
            active_simulation_count=num_simulations,
        )
        can_duplicate_val = compute_can_duplicate(user_role)

        api_scenarios.append(
            ListScenarioApiScenario(
                scenario_id=a.id,
                name=name_obj.name if name_obj else None,
                problem_statement=None,
                is_inactive=not a.active,
                generated=a.generated,
                mcp=a.mcp,
                department_ids=dept_ids_str,
                objective_ids=[str(oid) for oid in (a.objective_ids or [])],
                persona_ids=[str(pid) for pid in (a.persona_ids or [])],
                field_ids=[str(fid) for fid in (a.parameter_field_ids or [])],
                simulation_ids=[str(sid) for sid in (a.scenario_ids or [])],
                num_simulations=num_simulations,
                active_simulation_count=num_simulations,
                can_edit=can_edit_val,
                can_delete=can_delete_val,
                can_duplicate=can_duplicate_val,
                cohort_ids=None,
                updated_at=a.updated_at,
            )
        )

    # -- Step 7: Build facet sections --
    persona_filter = ListFilterSection(
        options=[
            ListFilterOption(
                id=str(getattr(p, "persona_id", None) or p.id),
                name=p.name,
                count=0,
            )
            for p in persona_facet
        ],
        selected_ids=[str(pid) for pid in persona_ids] if persona_ids else None,
        search=persona_search,
    )

    simulation_filter = ListFilterSection(
        options=[
            ListFilterOption(
                id=str(getattr(s, "simulation_id", None) or s.id),
                name=getattr(s, "name", None),
                count=0,
            )
            for s in simulation_facet
        ],
        selected_ids=[str(sid) for sid in simulation_ids] if simulation_ids else None,
        search=simulation_search,
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

    return ListScenarioApiResponse(
        actor_name=actor_name,
        scenarios=api_scenarios,
        objectives=api_objectives,
        fields=api_fields,
        cohorts=api_cohorts,
        personas=api_personas,
        simulations=api_simulations,
        departments=api_departments,
        persona_filter=persona_filter,
        simulation_filter=simulation_filter,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListScenarioApiResponse:
    return ListScenarioApiResponse(
        actor_name=actor_name,
        scenarios=[],
        objectives=[],
        fields=[],
        cohorts=[],
        personas=[],
        simulations=[],
        departments=[],
        total_count=total_count,
    )
