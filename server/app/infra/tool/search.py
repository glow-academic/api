"""Tool search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — agent_ids → tool resource IDs via agent artifacts
  3. search_tools — core artifact search (IDs + total_count)
  4. get_tools — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions
  6. Permissions — compute per-tool can_edit, can_delete, can_duplicate
  7. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.tool.types import (
    ListToolApiResponse,
    ListToolApiTool,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.tool.get import get_tools
from app.tools.artifacts.tool.search import search_tools
from app.tools.resources.agents.search import (
    search_agents as search_agents_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names

TOOL_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "My Tool",
        "description": "The tool's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "A description of the tool...",
        "description": "Optional description",
    },
]


async def search_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    filter_creatable: list[str] | None = None,
    # Facet search text
    department_search: str | None = None,
    agent_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListToolApiResponse:
    """Tool search using composable infra functions."""
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    actor_name = profile.name

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    tool_resource_ids: list[UUID] | None = None

    if filter_agent_ids:
        # agent_ids filter references agent_artifact IDs
        # Agents have tools_junction → get tool resource IDs
        from app.tools.artifacts.agent.get import (
            get_agents as get_agent_artifacts,
        )

        async with pool.acquire() as conn:
            agent_artifacts = await get_agent_artifacts(
                conn, filter_agent_ids, tools=True
            )
        tids: set[UUID] = set()
        for a in agent_artifacts:
            tids.update(a.tool_ids or [])
        if tids:
            tool_resource_ids = list(tids)
        else:
            return _empty_response(actor_name)

    # ── Step 3: Search tools ────────────────────────────────────────

    async with pool.acquire() as conn:
        tool_ids_list, total_count = await search_tools(
            conn,
            search=search,
            department_ids=filter_department_ids,
            tool_ids=tool_resource_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not tool_ids_list:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get tool artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        artifacts = await get_tools(
            conn,
            tool_ids_list,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
        )

    # ── Step 5: Parallel hydration + facets ────────────────────────────

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

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, tool=True, limit_count=100
            )

    async def _fetch_agent_facet() -> list:
        async with pool.acquire() as conn:
            return await search_agents_resource(
                conn, redis, search=agent_search, agent=True, limit_count=100
            )

    (
        names_data,
        descriptions_data,
        department_facet,
        agent_facet,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_department_facet(),
        _fetch_agent_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # ── Step 6: Build tool list with permissions ────────────────────

    tools_list: list[ListToolApiTool] = []

    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        can_edit = compute_can_edit(
            user_role=user_role,
            active_agent_count=0,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            active_agent_count=0,
        )
        can_duplicate = compute_can_duplicate(user_role)

        tools_list.append(
            ListToolApiTool(
                tool_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                updated_at=a.updated_at,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
            )
        )

    # ── Step 7: Build facet sections ───────────────────────────────────

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

    # Creatable filter: static boolean options
    creatable_filter = ListFilterSection(
        options=[
            ListFilterOption(id="true", name="Creatable", count=0),
            ListFilterOption(id="false", name="Non-Creatable", count=0),
        ],
        selected_ids=filter_creatable if filter_creatable else None,
    )

    return ListToolApiResponse(
        actor_name=actor_name,
        tools=tools_list,
        department_filter=department_filter,
        agent_filter=agent_filter,
        creatable_filter=creatable_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListToolApiResponse:
    return ListToolApiResponse(
        actor_name=actor_name,
        tools=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
