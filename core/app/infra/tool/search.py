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

from app.infra.api_types import ListFilterOption, ListFilterSection
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
from app.tools.artifacts.tool.get import get_tools
from app.tools.artifacts.tool.search import search_tools
from app.tools.resources.agents.search import search_agents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

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
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_creatable: list[str] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    agent_search: str | None = None,
    page_size: int = 12,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListToolApiResponse:
    """tool search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("tool/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "filter_creatable": sorted(filter_creatable) if filter_creatable else None,
            "filter_agent_ids": [str(x) for x in filter_agent_ids] if filter_agent_ids else None,
            "department_search": department_search,
            "flag_search": flag_search,
            "agent_search": agent_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "tool", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListToolApiResponse,
        builder=lambda: _search_tool_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_creatable=filter_creatable,
            filter_agent_ids=filter_agent_ids,
            department_search=department_search,
            flag_search=flag_search,
            agent_search=agent_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_tool_build(
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

        from app.tools.entries.soft_calls.search import search_soft_calls
        pending_entries = await search_soft_calls(
            conn, artifact="tool", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for tid in [*tool_ids_list, *pending_ledger_ids]:
        if tid in seen:
            continue
        seen.add(tid)
        merged_ids.append(tid)
    added = sum(1 for tid in pending_ledger_ids if tid not in set(tool_ids_list))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get tool artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        artifacts = await get_tools(
            conn,
            merged_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            permissions=True,
            active=None,
        )

    # Build per-tool agent_ids map (agent_artifact ids referencing this tool).
    # tool_agents_junction.agents_id → agents_resource.id; reverse-walk
    # agent_agents_junction.agents_id → agent_artifact.id.
    agent_ids_by_tool: dict[UUID, list[UUID]] = {}
    if merged_ids:
        async with pool.acquire() as conn:
            agent_rows = await conn.fetch(
                """
                SELECT taj.tool_id,
                       ARRAY_AGG(DISTINCT aaj.agent_id)
                         FILTER (WHERE aaj.agent_id IS NOT NULL) AS agent_ids
                FROM tool_agents_junction taj
                LEFT JOIN agent_agents_junction aaj
                  ON aaj.agents_id = taj.agents_id AND aaj.active = true
                WHERE taj.tool_id = ANY($1) AND taj.active = true
                GROUP BY taj.tool_id
                """,
                merged_ids,
            )
        for r in agent_rows:
            agent_ids_by_tool[r["tool_id"]] = list(r["agent_ids"] or [])

    # ── Step 5: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        return await get_descriptions(pool, all_description_ids, redis)

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

        ledger = ledger_by_artifact_id.get(a.id)
        tools_list.append(
            ListToolApiTool(
                tool_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                is_inactive=not a.active,
                flag_ids=list(a.flag_ids or []),
                permission_ids=list(a.permission_ids or []),
                agent_ids=list(agent_ids_by_tool.get(a.id, [])),
                department_ids=list(a.department_ids or []),
                updated_at=a.updated_at,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
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
        import_fields=TOOL_IMPORT_FIELDS,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListToolApiResponse:
    return ListToolApiResponse(
        actor_name=actor_name,
        tools=[],
        total_count=total_count,
        import_fields=TOOL_IMPORT_FIELDS,
    )


async def _empty_list() -> list:
    return []
