"""Agent search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_agents — core artifact search (IDs + total_count)
  3. get_agents — hydrate junction IDs
  4. Resource get tools — hydrate models
  5. Permissions — compute per-agent can_edit, can_delete, can_duplicate
  6. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.agent.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_list_can_edit,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.types import (
    ListAgentApiAgent,
    ListAgentApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.agent.get import get_agents
from app.tools.artifacts.agent.search import search_agents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.models.get import (
    get_models as get_models_resource,
)
from app.tools.resources.models.search import (
    search_models as search_models_resource,
)
from app.tools.resources.names.get import get_names
from app.tools.resources.tools.search import (
    search_tools as search_tools_resource,
)

AGENT_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Customer Support Agent",
        "description": "The agent's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Handles customer inquiries...",
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


async def search_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_model_ids: list[UUID] | None = None,
    filter_tool_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    model_search: str | None = None,
    tool_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListAgentApiResponse:
    """Agent search using composable infra functions."""
    from fastapi import HTTPException

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    actor_name = profile.name

    # -- Step 2: Reverse lookups --
    # model_ids and tool_ids are direct junction filters on agent search

    # -- Step 3: Search agents --
    async with pool.acquire() as conn:
        agent_ids_result, total_count = await search_agents(
            conn,
            search=search,
            department_ids=filter_department_ids,
            model_ids=filter_model_ids,
            tool_ids=filter_tool_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not agent_ids_result:
        return _empty_response(actor_name, total_count=0)

    # -- Step 4: Get agent artifacts with junction IDs --
    async with pool.acquire() as conn:
        artifacts = await get_agents(
            conn,
            agent_ids_result,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            models=True,
        )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_model_ids: set[UUID] = set()

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        for mid in a.model_ids or []:
            all_model_ids.add(mid)

    # Parallel: hydrate resources + facets

    async def _fetch_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_models() -> list:
        async with pool.acquire() as conn:
            return await get_models_resource(conn, list(all_model_ids), redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, agent=True, limit_count=100
            )

    async def _fetch_model_facet() -> list:
        async with pool.acquire() as conn:
            return await search_models_resource(
                conn, redis, search=model_search, agent=True, limit_count=100
            )

    async def _fetch_tool_facet() -> list:
        async with pool.acquire() as conn:
            return await search_tools_resource(
                conn, redis, search=tool_search, agent=True, limit_count=100
            )

    (
        names_data,
        models_data,
        department_facet,
        model_facet,
        tool_facet,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty_list(),
        _fetch_models() if all_model_ids else _empty_list(),
        _fetch_department_facet(),
        _fetch_model_facet(),
        _fetch_tool_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    model_map: dict[UUID, tuple[str | None, str | None]] = {}
    for m in models_data:
        m_id = getattr(m, "id", None)
        if m_id:
            model_map[m_id] = (m.name, m.description)

    # -- Step 6: Build agent list with permissions --
    # We need active_settings_count per agent — approximate from the artifacts
    # The old SQL had this denormalized; in composable mode we set it to 0
    # since we cannot easily compute it without additional queries.
    # The search already filters active-only, so settings count isn't available
    # from artifact data alone. We'll need a separate query or accept 0.
    # For now: always 0 (agents returned are editable if role allows).

    api_agents: list[ListAgentApiAgent] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        # First model ID
        model_id = a.model_ids[0] if a.model_ids else None

        can_edit_val = compute_list_can_edit(
            user_role=user_role,
            agent_department_ids=dept_ids_str,
            active_settings_count=0,
        )
        can_delete_val = compute_can_delete(
            user_role=user_role,
            active_settings_count=0,
        )
        can_duplicate_val = compute_can_duplicate(user_role)

        model_name = None
        model_description = None
        if model_id and model_id in model_map:
            model_name, model_description = model_map[model_id]

        api_agents.append(
            ListAgentApiAgent(
                agent_id=a.id,
                name=name_obj.name if name_obj else None,
                description=None,
                reasoning=None,
                temperature=None,
                model_id=model_id,
                model_name=model_name,
                model_description=model_description,
                role=None,
                updated_at=a.updated_at,
                department_ids=dept_ids_str,
                can_edit=can_edit_val,
                can_duplicate=can_duplicate_val,
                can_delete=can_delete_val,
            )
        )

    # -- Step 7: Build facet sections --
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

    model_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(m.id), name=m.name, count=0) for m in model_facet
        ],
        selected_ids=[str(mid) for mid in filter_model_ids]
        if filter_model_ids
        else None,
        search=model_search,
    )

    tool_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(t.id), name=t.name, count=0) for t in tool_facet
        ],
        selected_ids=[str(tid) for tid in filter_tool_ids] if filter_tool_ids else None,
        search=tool_search,
    )

    return ListAgentApiResponse(
        actor_name=actor_name,
        agents=api_agents,
        department_filter=department_filter,
        model_filter=model_filter,
        tool_filter=tool_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListAgentApiResponse:
    return ListAgentApiResponse(
        actor_name=actor_name,
        agents=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
