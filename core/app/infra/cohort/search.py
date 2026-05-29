"""Cohort search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — profile_ids, simulation_ids (direct junction filters)
  3. search_cohorts — core artifact search (IDs + total_count)
  4. get_cohorts — hydrate junction IDs
  5. Resource get tools — hydrate profiles, simulations, departments
  6. Permissions — compute per-cohort can_edit, can_delete, can_duplicate, can_leave
  7. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.cohort.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
    compute_can_leave,
)
from app.infra.cohort.types import (
    ListCohortApiCohort,
    ListCohortApiDepartment,
    ListCohortApiProfile,
    ListCohortApiResponse,
    ListCohortApiSimulation,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.artifacts.cohort.search import search_cohorts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.get import (
    get_profiles as get_profiles_resource,
)
from app.tools.resources.profiles.search import (
    search_profiles as search_profiles_resource,
)
from app.tools.resources.simulations.get import (
    get_simulations as get_simulations_resource,
)
from app.tools.resources.simulations.search import (
    search_simulations as search_simulations_resource,
)
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

COHORT_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Fall 2025 Cohort",
        "description": "The cohort's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "A cohort for fall 2025 students...",
        "description": "Optional description",
    },
    {
        "key": "is_inactive",
        "label": "Inactive",
        "type": "boolean",
        "example": "false",
        "description": "Whether the cohort is inactive (true/false)",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
    {
        "key": "simulations",
        "label": "Simulations",
        "multi": True,
        "example": "Emergency Triage, Patient Intake",
        "description": "Comma-separated simulation names",
    },
    {
        "key": "profiles",
        "label": "Profiles",
        "multi": True,
        "example": "John Doe, Jane Smith",
        "description": "Comma-separated profile names",
    },
]


async def search_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    search: str | None = None,
    filter_profile_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    profile_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 10,
    page_offset: int = 0,
    bypass_cache: bool = False,
) -> ListCohortApiResponse:
    """cohort search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("cohort/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_profile_ids": [str(x) for x in filter_profile_ids] if filter_profile_ids else None,
            "filter_simulation_ids": [str(x) for x in filter_simulation_ids] if filter_simulation_ids else None,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "profile_search": profile_search,
            "simulation_search": simulation_search,
            "department_search": department_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "cohort", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListCohortApiResponse,
        builder=lambda: _search_cohort_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_profile_ids=filter_profile_ids,
            filter_simulation_ids=filter_simulation_ids,
            filter_department_ids=filter_department_ids,
            profile_search=profile_search,
            simulation_search=simulation_search,
            department_search=department_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_cohort_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_profile_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    profile_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    # Pagination
    page_size: int = 10,
    page_offset: int = 0,
) -> ListCohortApiResponse:
    """Cohort search using composable infra functions."""
    from fastapi import HTTPException

    # -- Step 1: Profile context --
    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids
    actor_name = profile.name
    user_profiles_id = profile.profiles_id

    # -- Step 2: Reverse lookups --
    # filter_profile_ids are profiles_resource IDs — direct junction filter
    # filter_simulation_ids are simulations_resource IDs — direct junction filter

    # -- Step 3: Search cohorts --
    with timed("query"):
     async with pool.acquire() as conn:
        cohort_ids_result, total_count = await search_cohorts(
            conn,
            search=search,
            department_ids=filter_department_ids,
            profile_ids=filter_profile_ids,
            simulation_ids=filter_simulation_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    # Pending ledger entries — see project_soft_calls_entry_pattern.
    from app.tools.entries.soft_calls.search import search_soft_calls
    async with pool.acquire() as conn:
        pending_entries = await search_soft_calls(
            conn, redis, artifact="cohort", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for cid in [*cohort_ids_result, *pending_ledger_ids]:
        if cid in seen:
            continue
        seen.add(cid)
        merged_ids.append(cid)
    added = sum(1 for cid in pending_ledger_ids if cid not in set(cohort_ids_result))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 4: Get cohort artifacts with junction IDs --
    async with pool.acquire() as conn:
        artifacts = await get_cohorts(
            conn,
            merged_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            profiles=True,
            simulations=True,
            active=None,
        )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_profile_ids: set[UUID] = set()
    all_simulation_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        for pid in a.profiles_ids or []:
            all_profile_ids.add(pid)
        for sid in a.simulation_ids or []:
            all_simulation_ids.add(sid)
        for did in a.department_ids or []:
            all_department_ids.add(did)

    # Parallel: hydrate resources + facets

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        return await get_profiles_resource(pool, list(all_profile_ids), redis)

    async def _fetch_simulations() -> list:
        if not all_simulation_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulations_resource(conn, list(all_simulation_ids), redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        return await get_departments(pool, list(all_department_ids), redis)

    async def _fetch_profile_facet() -> list:
        async with pool.acquire() as conn:
            return await search_profiles_resource(
                conn, redis, search=profile_search, cohort=True, limit_count=100
            )

    async def _fetch_simulation_facet() -> list:
        async with pool.acquire() as conn:
            return await search_simulations_resource(
                conn, redis, search=simulation_search, cohort=True, limit_count=100
            )

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, cohort=True, limit_count=100
            )

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, cohort=True, limit_count=100
            )

    with timed("hydrate"):
        (
            names_data,
            profiles_data,
            simulations_data,
            departments_data,
            profile_facet,
            simulation_facet,
            department_facet,
            flag_facet,
        ) = await asyncio.gather(
            _fetch_names(),
            _fetch_profiles(),
            _fetch_simulations(),
            _fetch_departments(),
            _fetch_profile_facet(),
            _fetch_simulation_facet(),
            _fetch_department_facet(),
            _fetch_flag_facet(),
        )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}

    # Build mapping arrays
    api_profiles: list[ListCohortApiProfile] = [
        ListCohortApiProfile(
            profile_id=p.id,
            name=p.name,
            description=getattr(p, "description", None) or "",
        )
        for p in profiles_data
    ]

    api_simulations: list[ListCohortApiSimulation] = [
        ListCohortApiSimulation(
            simulation_id=s.id,
            name=getattr(s, "name", None),
            description=s.description,
            department_ids=[str(d) for d in (getattr(s, "department_ids", None) or [])],
        )
        for s in simulations_data
    ]

    api_departments: list[ListCohortApiDepartment] = [
        ListCohortApiDepartment(
            department_id=d.id,
            name=d.name,
            description=d.description,
        )
        for d in departments_data
    ]

    # -- Step 6: Build cohort list with permissions --
    api_cohorts: list[ListCohortApiCohort] = []
    with timed("build"):
     for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        profile_ids_str = [str(p) for p in (a.profiles_ids or [])]
        sim_ids_str = [str(s) for s in (a.simulation_ids or [])]

        # Check if current user is a member of this cohort
        is_member = user_profiles_id in set(a.profiles_ids or [])

        can_edit_val = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=dept_ids_str,
            user_department_ids=user_department_ids,
        )
        can_delete_val = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=dept_ids_str,
            usage_count=len(a.profiles_ids or []),
        )
        can_duplicate_val = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)
        can_leave_val = compute_can_leave(is_member=is_member)

        ledger = ledger_by_artifact_id.get(a.id)
        api_cohorts.append(
            ListCohortApiCohort(
                id=a.id,

                cohort_id=a.id,
                name=name_obj.name if name_obj else None,
                description=None,
                is_inactive=not a.active,
                generated=a.generated,
                mcp=a.mcp,
                department_ids=dept_ids_str,
                profile_ids=profile_ids_str,
                simulation_ids=sim_ids_str,
                usage_count=len(a.profiles_ids or []),
                num_members=len(a.profiles_ids or []),
                can_edit=can_edit_val,
                can_delete=can_delete_val,
                can_duplicate=can_duplicate_val,
                can_leave=can_leave_val,
                updated_at=a.updated_at,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    # -- Step 7: Build facet sections --
    profile_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(p.id), name=p.name, count=0) for p in profile_facet
        ],
        selected_ids=[str(pid) for pid in filter_profile_ids]
        if filter_profile_ids
        else None,
        search=profile_search,
    )

    simulation_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=getattr(s, "name", None), count=0)
            for s in simulation_facet
        ],
        selected_ids=[str(sid) for sid in filter_simulation_ids]
        if filter_simulation_ids
        else None,
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

    return ListCohortApiResponse(
        actor_name=actor_name,
        cohorts=api_cohorts,
        profiles=api_profiles,
        simulations=api_simulations,
        departments=api_departments,
        simulation_filter=simulation_filter,
        profile_filter=profile_filter,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
        import_fields=COHORT_IMPORT_FIELDS,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListCohortApiResponse:
    return ListCohortApiResponse(
        actor_name=actor_name,
        cohorts=[],
        profiles=[],
        simulations=[],
        departments=[],
        total_count=total_count,
        import_fields=COHORT_IMPORT_FIELDS,
    )


async def _empty_list() -> list:
    return []
