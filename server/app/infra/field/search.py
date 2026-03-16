"""Field search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_fields — core artifact search (IDs + total_count)
  3. get_fields — hydrate junction IDs
  4. Resource get tools — hydrate names, descriptions
  5. Permissions — compute per-field can_edit, can_delete, can_duplicate
  6. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.field.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.field.types import (
    ListFieldApiField,
    ListFieldApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.field.search import search_fields
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.parameters.search import (
    search_parameters as search_parameters_resource,
)
from app.tools.resources.personas.search import (
    search_personas as search_personas_resource,
)

FIELD_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Communication Skills",
        "description": "The field's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Assesses verbal and non-verbal communication...",
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


async def search_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    parameter_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    parameter_search: str | None = None,
    persona_search: str | None = None,
    department_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListFieldApiResponse:
    """Field search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, departments, name
      2. search_fields -> (field_artifact_ids, total_count)
      3. get_fields -> hydrate junction IDs
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

    # -- Step 2: Search fields --
    # The artifact search tool handles parameter_ids and persona_ids filters internally

    async with pool.acquire() as conn:
        field_ids, total_count = await search_fields(
            conn,
            search=search,
            department_ids=filter_department_ids,
            parameter_ids=parameter_ids,
            persona_ids=persona_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not field_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 3: Get field artifacts with junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_fields(
            conn,
            field_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            conditional_parameters=True,
            fields=True,
        )

    # -- Step 4: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_parameter_facet() -> list:
        async with pool.acquire() as conn:
            return await search_parameters_resource(
                conn, redis, search=parameter_search, parameter=True, limit_count=100
            )

    async def _fetch_persona_facet() -> list:
        async with pool.acquire() as conn:
            return await search_personas_resource(
                conn, redis, search=persona_search, persona=True, limit_count=100
            )

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, field=True, limit_count=100
            )

    # Per-field permissions context (gives us active_parameter_count)
    async def _fetch_perm(artifact_id: UUID) -> object:
        async with pool.acquire() as conn:
            return await resolve_field_permissions_context(conn, artifact_id)

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]

    (
        names_data,
        descriptions_data,
        parameter_facet,
        persona_facet,
        department_facet,
        *perm_results,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_parameter_facet(),
        _fetch_persona_facet(),
        _fetch_department_facet(),
        *perm_tasks,
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # -- Step 5: Build field list with permissions --

    fields: list[ListFieldApiField] = []

    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_param_count = perm_results[i].active_parameter_count

        is_inactive = not a.active

        can_edit = compute_can_edit(
            user_role=user_role,
            field_department_ids=dept_ids_str,
            active_parameter_count=active_param_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            field_department_ids=dept_ids_str,
            active_parameter_count=active_param_count,
        )
        can_duplicate = compute_can_duplicate(user_role)

        fields.append(
            ListFieldApiField(
                field_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                conditional_parameter_ids=a.conditional_parameter_ids,
                persona_ids=None,
                is_inactive=is_inactive,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # -- Step 6: Build facet sections --

    parameter_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(p.id), name=p.name, count=0)
            for p in parameter_facet
        ],
        selected_ids=[str(pid) for pid in parameter_ids] if parameter_ids else None,
        search=parameter_search,
    )

    persona_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(p.id), name=p.name, count=0) for p in persona_facet
        ],
        selected_ids=[str(pid) for pid in persona_ids] if persona_ids else None,
        search=persona_search,
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

    return ListFieldApiResponse(
        actor_name=actor_name,
        fields=fields,
        parameter_filter=parameter_filter,
        persona_filter=persona_filter,
        department_filter=department_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListFieldApiResponse:
    return ListFieldApiResponse(
        actor_name=actor_name,
        fields=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
