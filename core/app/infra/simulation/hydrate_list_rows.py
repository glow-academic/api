"""Hydrate ``ListSimulationApiSimulation`` rows for a specific set of simulation ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_simulation_build``'s flow: the row
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
from app.infra.simulation.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.simulation.types import ListSimulationApiSimulation
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.resources.cohorts.search import (
    search_cohorts as search_cohorts_resource,
)
from app.tools.resources.flags.get import get_flags
from app.tools.resources.names.get import get_names


async def hydrate_simulation_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    simulation_ids: list[UUID],
) -> list[ListSimulationApiSimulation]:
    """Return ``ListSimulationApiSimulation`` rows for the given simulation ids.

    Mirrors ``_search_simulation_build``'s row-hydration steps minus
    facets and pagination. Cohort usage counts are computed from the
    same cohort facet ``/simulation/search`` uses, so they stay
    accurate for both fresh and updated rows.
    """
    if not simulation_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_simulations(
            conn,
            simulation_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            scenarios=True,
            simulations=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="simulation", artifact_ids=simulation_ids,
            limit=len(simulation_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_flag_ids: set[UUID] = set()
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        for fid in a.flag_ids or []:
            all_flag_ids.add(fid)

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _flag_rows() -> list:
        return (
            await get_flags(pool, list(all_flag_ids), redis) if all_flag_ids else []
        )

    async def _cohort_facet() -> list:
        # Used only to compute num_cohorts / cohort_usage_count per
        # row — the same facet ``/simulation/search`` queries. Capped
        # at 100 (matches search).
        async with pool.acquire() as conn:
            return await search_cohorts_resource(
                conn, redis, cohort=True, limit_count=100,
            )

    names_data, flag_rows_data, cohort_facet = await asyncio.gather(
        _names(), _flag_rows(), _cohort_facet(),
    )

    name_map = {n.id: n for n in names_data}
    flag_meta_map: dict[UUID, tuple[str | None, bool | None]] = {
        f.id: (getattr(f, "type", None), getattr(f, "value", None))
        for f in flag_rows_data
        if getattr(f, "id", None)
    }

    rows: list[ListSimulationApiSimulation] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        sim_resource_ids = set(a.simulation_ids or [])
        cohort_usage = sum(
            1 for c in cohort_facet
            if sim_resource_ids & set(c.simulation_ids or [])
        )

        # is_inactive mirrors the artifact-level active flag.
        # is_practice comes from the practice flag selected via flag_ids.
        is_inactive = not a.active
        is_practice = False
        for fid in a.flag_ids or []:
            ftype, fvalue = flag_meta_map.get(fid, (None, None))
            if ftype == "practice" and fvalue is True:
                is_practice = True
                break

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            simulation_department_ids=dept_ids_str,
            cohort_usage_count=cohort_usage,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            simulation_department_ids=dept_ids_str,
            cohort_usage_count=cohort_usage,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListSimulationApiSimulation(
                simulation_id=a.id,
                name=name_obj.name if name_obj else None,
                description=None,
                department_ids=dept_ids_str,
                flag_ids=list(a.flag_ids or []),
                is_inactive=is_inactive,
                is_practice=is_practice,
                practice_simulation=is_practice,
                generated=a.generated,
                mcp=a.mcp,
                scenario_ids=[str(sid) for sid in (a.scenario_ids or [])],
                num_cohorts=cohort_usage,
                cohort_usage_count=cohort_usage,
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
