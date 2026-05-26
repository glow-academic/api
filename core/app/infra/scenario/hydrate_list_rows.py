"""Hydrate ``ListScenarioApiScenario`` rows for a specific set of scenario ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_scenario_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names →
compute permissions), without the facet aggregation, pagination, or
big-cache wrap that the search route layers on top.
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
from app.infra.scenario.types import ListScenarioApiScenario
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.resources.names.get import get_names
from app.tools.resources.simulations.search import (
    search_simulations as search_simulations_resource,
)


async def hydrate_scenario_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    scenario_ids: list[UUID],
) -> list[ListScenarioApiScenario]:
    """Return ``ListScenarioApiScenario`` rows for the given scenario ids.

    Mirrors ``_search_scenario_build``'s row-hydration steps minus facets
    and pagination. Active simulation counts are computed from the same
    simulation facet ``/scenario/search`` uses, so they stay accurate
    for both fresh and updated rows.
    """
    if not scenario_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_scenarios(
            conn,
            scenario_ids,
            names=True,
            descriptions=True,
            departments=True,
            objectives=True,
            personas=True,
            parameter_fields=True,
            scenarios=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="scenario", artifact_ids=scenario_ids,
            limit=len(scenario_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _simulations_facet() -> list:
        # Used only to compute num_simulations / active_simulation_count
        # per row — the same facet ``/scenario/search`` queries. Capped
        # at 100 (matches search).
        async with pool.acquire() as conn:
            return await search_simulations_resource(
                conn, redis, simulation=True, limit_count=100,
            )

    names_data, simulation_facet = await asyncio.gather(
        _names(), _simulations_facet(),
    )

    name_map = {n.id: n for n in names_data}

    rows: list[ListScenarioApiScenario] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        scenario_resource_set = set(a.scenario_ids or [])
        num_simulations = sum(
            1 for sf in simulation_facet
            if scenario_resource_set & set(sf.scenario_ids or [])
        )

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            scenario_department_ids=dept_ids_str,
            active_simulation_count=num_simulations,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            scenario_department_ids=dept_ids_str,
            active_simulation_count=num_simulations,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListScenarioApiScenario(
                scenario_id=a.id,
                name=name_obj.name if name_obj else None,
                problem_statement=None,
                is_inactive=is_inactive,
                generated=a.generated,
                mcp=a.mcp,
                department_ids=dept_ids_str,
                objective_ids=[str(oid) for oid in (a.objective_ids or [])],
                persona_ids=[str(pid) for pid in (a.persona_ids or [])],
                field_ids=[str(fid) for fid in (a.parameter_field_ids or [])],
                simulation_ids=[str(sid) for sid in (a.scenario_ids or [])],
                num_simulations=num_simulations,
                active_simulation_count=num_simulations,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                cohort_ids=None,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
                updated_at=a.updated_at,
            )
        )

    return rows
