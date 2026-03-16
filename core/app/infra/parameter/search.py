"""Parameter search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_parameters — core artifact search (IDs + total_count)
  3. get_parameters — hydrate junction IDs
  4. Resource get tools — hydrate names, descriptions
  5. Permissions — compute per-parameter can_edit, can_delete, can_duplicate
  6. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.parameter.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.parameter.permissions_context import (
    ParameterPermissionsContext,
    resolve_parameter_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.parameter.types import (
    ListParameterApiParameter,
    ListParameterApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.artifacts.parameter.search import search_parameters
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.fields.get import get_fields as get_fields_resource
from app.tools.resources.fields.search import (
    search_fields as search_fields_resource,
)
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenarios_resource,
)

PARAMETER_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Vital Signs",
        "description": "The parameter's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Measures vital signs...",
        "description": "Optional description",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
]


async def search_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListParameterApiResponse:
    """Parameter search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, departments, name
      2. search_parameters -> (parameter_artifact_ids, total_count)
      3. get_parameters -> hydrate junction IDs
      4. Parallel: hydrate resources + compute permissions + facets
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

    # -- Step 2: Search parameters --
    # The artifact search tool handles scenario_ids and field_ids filters internally

    async with pool.acquire() as conn:
        parameter_ids, total_count = await search_parameters(
            conn,
            search=search,
            department_ids=filter_department_ids,
            scenario_ids=scenario_ids,
            field_ids=field_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not parameter_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 3: Get parameter artifacts with junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_parameters(
            conn,
            parameter_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            fields=True,
            parameters=True,
        )

    # -- Step 4: Parallel hydration + facets + usage counts --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_field_junction_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_field_junction_ids.extend(a.field_ids or [])

    # Per-parameter permissions context (gives us active_scenario_count)
    async def _get_names_data() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions_data() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_parameter_fields_data() -> list:
        if not all_field_junction_ids:
            return []
        async with pool.acquire() as conn:
            return await get_parameter_fields(conn, all_field_junction_ids, redis)

    async def _search_scenarios() -> list:
        async with pool.acquire() as conn:
            return await search_scenarios_resource(
                conn, redis, search=scenario_search, scenario=True, limit_count=100
            )

    async def _search_fields() -> list:
        async with pool.acquire() as conn:
            return await search_fields_resource(
                conn, redis, search=field_search, parameter=True, limit_count=100
            )

    async def _search_depts() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, parameter=True, limit_count=100
            )

    async def _get_perm(artifact_id: UUID) -> ParameterPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_parameter_permissions_context(conn, artifact_id)

    perm_tasks = [_get_perm(a.id) for a in artifacts]

    (
        names_data,
        descriptions_data,
        parameter_fields_data,
        scenario_facet,
        field_facet,
        department_facet,
        *perm_results,
    ) = await asyncio.gather(
        _get_names_data(),
        _get_descriptions_data(),
        _get_parameter_fields_data(),
        _search_scenarios(),
        _search_fields(),
        _search_depts(),
        *perm_tasks,
    )

    # Hydrate field names for sample_items
    all_fields_resource_ids = list({pf.field_id for pf in parameter_fields_data})
    async with pool.acquire() as conn:
        fields_resource_data = (
            await get_fields_resource(conn, all_fields_resource_ids, redis)
            if all_fields_resource_ids
            else []
        )
    field_name_map: dict[UUID, str] = {f.id: f.name for f in fields_resource_data}
    # Map parameter_fields_resource ID -> field name
    pf_id_to_name: dict[UUID, str] = {}
    for pf in parameter_fields_data:
        name = field_name_map.get(pf.field_id)
        if name:
            pf_id_to_name[pf.id] = name

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # -- Step 5: Build parameter list with permissions --

    parameters: list[ListParameterApiParameter] = []

    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_scenario_count = perm_results[i].active_scenario_count

        can_edit = compute_can_edit(
            user_role=user_role,
            parameter_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            parameter_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
        )
        can_duplicate = compute_can_duplicate(user_role)

        parameters.append(
            ListParameterApiParameter(
                parameter_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                department_ids=dept_ids_str,
                scenario_ids=None,
                num_items=len(a.field_ids or []),
                sample_items=[
                    pf_id_to_name[fid]
                    for fid in (a.field_ids or [])[:3]
                    if fid in pf_id_to_name
                ],
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # -- Step 6: Build facet sections --

    scenario_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0) for s in scenario_facet
        ],
        selected_ids=[str(sid) for sid in scenario_ids] if scenario_ids else None,
        search=scenario_search,
    )

    field_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, count=0) for f in field_facet
        ],
        selected_ids=[str(fid) for fid in field_ids] if field_ids else None,
        search=field_search,
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

    return ListParameterApiResponse(
        actor_name=actor_name,
        parameters=parameters,
        scenario_filter=scenario_filter,
        field_filter=field_filter,
        department_filter=department_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListParameterApiResponse:
    return ListParameterApiResponse(
        actor_name=actor_name,
        parameters=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
