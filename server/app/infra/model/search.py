"""Model search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — agent_ids → model resource IDs via agent artifacts
  3. search_models — core artifact search (IDs + total_count)
  4. get_models — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions, providers_resource
  6. Permissions — compute per-model can_edit, can_delete, can_duplicate
  7. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.model.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.model.types import (
    ListModelApiModel,
    ListModelApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.model.get import get_models
from app.tools.artifacts.model.search import search_models
from app.tools.resources.agents.search import (
    search_agents as search_agents_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.providers.get import (
    get_providers as get_providers_resource,
)
from app.tools.resources.providers.search import (
    search_providers as search_providers_resource,
)

MODEL_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "GPT-4o",
        "description": "The model's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "OpenAI's flagship multimodal model...",
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


async def search_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_provider_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    # Facet search text
    provider_search: str | None = None,
    department_search: str | None = None,
    agent_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListModelApiResponse:
    """Model search using composable infra functions."""
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    model_resource_ids: list[UUID] | None = None

    if filter_agent_ids:
        # agent_ids filter references agent_artifact IDs
        # Agents have models_junction → get model resource IDs
        from app.tools.artifacts.agent.get import (
            get_agents as get_agent_artifacts,
        )

        async with pool.acquire() as conn:
            agent_artifacts = await get_agent_artifacts(
                conn, filter_agent_ids, models=True
            )
        mids: set[UUID] = set()
        for a in agent_artifacts:
            mids.update(a.model_ids or [])
        if mids:
            model_resource_ids = list(mids)
        else:
            return _empty_response(actor_name)

    # ── Step 3: Search models ────────────────────────────────────────

    async with pool.acquire() as conn:
        model_ids_list, total_count = await search_models(
            conn,
            search=search,
            department_ids=filter_department_ids,
            provider_ids=filter_provider_ids,
            model_ids=model_resource_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not model_ids_list:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get model artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        artifacts = await get_models(
            conn,
            model_ids_list,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            providers=True,
        )

    # ── Step 5: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_provider_resource_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_provider_resource_ids.extend(a.provider_ids or [])

    async def _fetch_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_providers_resource() -> list:
        async with pool.acquire() as conn:
            return await get_providers_resource(conn, all_provider_resource_ids, redis)

    async def _fetch_provider_facet() -> list:
        async with pool.acquire() as conn:
            return await search_providers_resource(
                conn, redis, search=provider_search, model=True, limit_count=100
            )

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, model=True, limit_count=100
            )

    async def _fetch_agent_facet() -> list:
        async with pool.acquire() as conn:
            return await search_agents_resource(
                conn, redis, search=agent_search, agent=True, limit_count=100
            )

    (
        names_data,
        descriptions_data,
        providers_resource_data,
        provider_facet,
        department_facet,
        agent_facet,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty_list(),
        _fetch_descriptions() if all_description_ids else _empty_list(),
        _fetch_providers_resource() if all_provider_resource_ids else _empty_list(),
        _fetch_provider_facet(),
        _fetch_department_facet(),
        _fetch_agent_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    provider_resource_map = {p.id: p for p in providers_resource_data}

    # Agent count per model: the old SQL computed active_agent_count inline.
    # In the composable pattern we pass 0 — the search already filters models,
    # and can_edit on the list page is advisory (the save endpoint re-checks).

    # ── Step 6: Build model list with permissions ────────────────────

    models_list: list[ListModelApiModel] = []

    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        # Resolve provider name and base_url from provider_resource
        provider_id: UUID | None = None
        provider_name: str | None = None
        base_url: str | None = None
        if a.provider_ids:
            pr = provider_resource_map.get(a.provider_ids[0])
            if pr:
                provider_id = pr.id
                provider_name = pr.name
                base_url = pr.endpoint or ""

        dept_ids = [str(d) for d in (a.department_ids or [])]

        can_edit = compute_can_edit(
            user_role=user_role,
            model_department_ids=dept_ids,
            active_agent_count=0,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            model_department_ids=dept_ids,
            active_agent_count=0,
        )
        can_duplicate = compute_can_duplicate(user_role)

        models_list.append(
            ListModelApiModel(
                model_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                provider_id=provider_id,
                provider_name=provider_name,
                base_url=base_url,
                department_ids=dept_ids,
                is_inactive=not a.active,
                active=a.active,
                image_model=None,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # ── Step 7: Build facet sections ───────────────────────────────────

    provider_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(p.id), name=p.name, count=0) for p in provider_facet
        ],
        selected_ids=[str(pid) for pid in filter_provider_ids]
        if filter_provider_ids
        else None,
        search=provider_search,
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

    agent_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(a.id), name=a.name, count=0) for a in agent_facet
        ],
        selected_ids=[str(aid) for aid in filter_agent_ids]
        if filter_agent_ids
        else None,
        search=agent_search,
    )

    return ListModelApiResponse(
        actor_name=actor_name,
        models=models_list,
        provider_filter=provider_filter,
        department_filter=department_filter,
        agent_filter=agent_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListModelApiResponse:
    return ListModelApiResponse(
        actor_name=actor_name,
        models=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
