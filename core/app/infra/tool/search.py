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
from app.infra.api_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.tool.get import get_tools
from app.tools.artifacts.tool.search import search_tools
from app.tools.resources.agents.search import search_agents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
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
    filter_creatable: list[str] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    flag_search: str | None = None,
    agent_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
    **_kwargs,
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

    user_role_level = profile.role_level
    actor_name = profile.name

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    # filter_agent_ids reverse-lookup is not yet wired — agents reference
    # tools_resource IDs while the artifact list is keyed on tool_artifact IDs,
    # which requires a separate cross-walk. The agent_filter facet is exposed
    # so the client can render the picker; selection-driven filtering is a
    # follow-up.
    tool_resource_ids: list[UUID] | None = None

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

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, tool=True, limit_count=100
            )

    async def _fetch_agent_facet() -> list:
        """Agents that reference at least one tool. Filters to the names+ids
        the client needs to render an agent picker on the tools list page."""
        async with pool.acquire() as conn:
            agent_rows = await search_agents(
                conn,
                redis,
                search=agent_search,
                limit_count=200,
            )
        # Keep only agents that actually reference a tool; otherwise the picker
        # would be cluttered with agents that have nothing to filter against.
        return [a for a in agent_rows if getattr(a, "tool_ids", None)]

    (
        names_data,
        descriptions_data,
        department_facet,
        flag_facet,
        agent_facet,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_department_facet(),
        _fetch_flag_facet(),
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
            role_level=user_role_level, role_permissions=profile.role_permissions,
            active_agent_count=0,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            active_agent_count=0,
        )
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        tools_list.append(
            ListToolApiTool(
                tool_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                is_inactive=not a.active,
                flag_ids=list(a.flag_ids or []),
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

    # Creatable filter: static boolean options
    creatable_filter = ListFilterSection(
        options=[
            ListFilterOption(id="true", name="Creatable", count=0),
            ListFilterOption(id="false", name="Non-Creatable", count=0),
        ],
        selected_ids=filter_creatable if filter_creatable else None,
    )

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    agent_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(ag.id), name=ag.name, count=0) for ag in agent_facet
        ],
        selected_ids=[str(aid) for aid in filter_agent_ids] if filter_agent_ids else None,
        search=agent_search,
    )

    return ListToolApiResponse(
        actor_name=actor_name,
        tools=tools_list,
        department_filter=department_filter,
        creatable_filter=creatable_filter,
        agent_filter=agent_filter,
        flag_filter=flag_filter,
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
