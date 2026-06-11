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
from app.infra.agent.types import (
    ListAgentApiAgent,
    ListAgentApiResponse,
)
from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.artifact_scope import clamp_artifacts_to_actor_scope
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.agent.get import get_agents
from app.tools.artifacts.agent.search import search_agents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
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
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
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
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_model_ids: list[UUID] | None = None,
    filter_tool_ids: list[UUID] | None = None,
    department_search: str | None = None,
    model_search: str | None = None,
    tool_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 12,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListAgentApiResponse:
    """agent search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("agent/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "filter_model_ids": [str(x) for x in filter_model_ids] if filter_model_ids else None,
            "filter_tool_ids": [str(x) for x in filter_tool_ids] if filter_tool_ids else None,
            "department_search": department_search,
            "model_search": model_search,
            "tool_search": tool_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "agent", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListAgentApiResponse,
        builder=lambda: _search_agent_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_model_ids=filter_model_ids,
            filter_tool_ids=filter_tool_ids,
            department_search=department_search,
            model_search=model_search,
            tool_search=tool_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_agent_build(
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
    flag_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListAgentApiResponse:
    """Agent search using composable infra functions."""
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
    actor_name = profile.name

    # -- Step 2: Reverse lookups --
    # model_ids and tool_ids are direct junction filters on agent search

    # -- Step 3: Search agents --
    with timed("search_agents"):
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

    # -- Step 3a: Pending ledger entries -- mirrors persona/search.py
    from app.tools.entries.soft_calls.search import search_soft_calls
    with timed("pending_ledger"):
     async with pool.acquire() as conn:
        pending_entries = await search_soft_calls(
            conn, redis, artifact="agent", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for aid in [*agent_ids_result, *pending_ledger_ids]:
        if aid in seen:
            continue
        seen.add(aid)
        merged_ids.append(aid)
    added = sum(1 for aid in pending_ledger_ids if aid not in set(agent_ids_result))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 4: Get agent artifacts with junction IDs --
    # ``active=None`` so dormant pending-create rows come back too.
    with timed("get_agents"):
     async with pool.acquire() as conn:
        artifacts = await get_agents(
            conn,
            merged_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            models=True,
            active=None,
        )

    # -- Step 4b: Actor department-scope clamp --
    # Mirror the agent DETAIL ``get`` ``has_access`` gate on the LIST path so
    # cross-department agents the caller could not open in detail are not
    # leaked here; ``total_count`` is decremented by the rows removed.
    artifacts, total_count = clamp_artifacts_to_actor_scope(
        artifacts, user_role_level, profile.department_ids, total_count
    )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_model_ids: set[UUID] = set()
    all_flag_ids: set[UUID] = set()

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        for mid in a.model_ids or []:
            all_model_ids.add(mid)
        for fid in a.flag_ids or []:
            all_flag_ids.add(fid)

    # Parallel: hydrate resources + facets

    async def _fetch_names() -> list:
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_models() -> list:
        async with pool.acquire() as conn:
            return await get_models_resource(conn, list(all_model_ids), redis)

    async def _fetch_flag_rows() -> list:
        if not all_flag_ids:
            return []
        return await get_flags(pool, list(all_flag_ids), redis)

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

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, agent=True, limit_count=100
            )

    with timed("hydrate_and_facets"):
        (
            names_data,
            models_data,
            flag_rows_data,
            department_facet,
            model_facet,
            tool_facet,
            flag_facet,
        ) = await asyncio.gather(
            _fetch_names() if all_name_ids else _empty_list(),
            _fetch_models() if all_model_ids else _empty_list(),
            _fetch_flag_rows(),
            _fetch_department_facet(),
            _fetch_model_facet(),
            _fetch_tool_facet(),
            _fetch_flag_facet(),
        )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    model_map: dict[UUID, tuple[str | None, str | None]] = {}
    for m in models_data:
        m_id = getattr(m, "id", None)
        if m_id:
            model_map[m_id] = (m.name, m.description)

    # Flag id -> (type, value) for per-row boolean derivation
    flag_meta_map: dict[UUID, tuple[str | None, bool | None]] = {
        f.id: (getattr(f, "type", None), getattr(f, "value", None))
        for f in flag_rows_data
        if getattr(f, "id", None)
    }

    # -- Step 6: Build agent list with permissions --
    # We need active_settings_count per agent — approximate from the artifacts
    # The old SQL had this denormalized; in composable mode we set it to 0
    # since we cannot easily compute it without additional queries.
    # The search already filters active-only, so settings count isn't available
    # from artifact data alone. We'll need a separate query or accept 0.
    # For now: always 0 (agents returned are editable if role allows).

    with timed("assemble"):
     api_agents: list[ListAgentApiAgent] = []
     for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        # First model ID
        model_id = a.model_ids[0] if a.model_ids else None

        can_edit_val = compute_list_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            agent_department_ids=dept_ids_str,
            active_settings_count=0,
        )
        can_delete_val = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            active_settings_count=0,
        )
        can_duplicate_val = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        model_name = None
        model_description = None
        if model_id and model_id in model_map:
            model_name, model_description = model_map[model_id]

        # is_inactive mirrors artifact-level active flag (matches Document/Tool).
        # is_mcp comes from the mcp flag selected via flag_ids.
        is_inactive = not a.active
        is_mcp = False
        for fid in a.flag_ids or []:
            ftype, fvalue = flag_meta_map.get(fid, (None, None))
            if ftype == "mcp" and fvalue is True:
                is_mcp = True
                break

        ledger = ledger_by_artifact_id.get(a.id)
        api_agents.append(
            ListAgentApiAgent(
                id=a.id,

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
                flag_ids=list(a.flag_ids or []),
                is_inactive=is_inactive,
                is_mcp=is_mcp,
                can_edit=can_edit_val,
                can_duplicate=can_duplicate_val,
                can_delete=can_delete_val,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
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

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListAgentApiResponse(
        actor_name=actor_name,
        agents=api_agents,
        department_filter=department_filter,
        model_filter=model_filter,
        tool_filter=tool_filter,
        flag_filter=flag_filter,
        total_count=total_count,
        import_fields=AGENT_IMPORT_FIELDS,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListAgentApiResponse:
    return ListAgentApiResponse(
        actor_name=actor_name,
        agents=[],
        total_count=total_count,
        import_fields=AGENT_IMPORT_FIELDS,
    )


async def _empty_list() -> list:
    return []
