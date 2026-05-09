"""Hydrate ``ListToolApiTool`` rows for a specific set of tool ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_tool_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.tool.types import ListToolApiTool
from app.tools.artifacts.tool.get import get_tools
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names


async def hydrate_tool_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    tool_ids: list[UUID],
) -> list[ListToolApiTool]:
    """Return ``ListToolApiTool`` rows for the given tool ids.

    Mirrors ``_search_tool_build``'s row-hydration steps minus facets
    and pagination. ``active_agent_count`` is reported as 0 (the tool is
    brand-new or just edited; the agent linkage count is server-side
    materialized and reconciles on next page-level search).
    """
    if not tool_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

    async with pool.acquire() as conn:
        artifacts = await get_tools(
            conn,
            tool_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            permissions=True,
        )

    if not artifacts:
        return []

    # Per-tool agent_ids map (agent_artifact ids referencing this tool).
    # Mirrors the same reverse-walk ``_search_tool_build`` does so the
    # hydrated row carries the full agent linkage the client expects.
    agent_ids_by_tool: dict[UUID, list[UUID]] = {}
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
            tool_ids,
        )
    for r in agent_rows:
        agent_ids_by_tool[r["tool_id"]] = list(r["agent_ids"] or [])

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    names_data, descriptions_data = await asyncio.gather(_names(), _descs())

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListToolApiTool] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            active_agent_count=0,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            active_agent_count=0,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        rows.append(
            ListToolApiTool(
                tool_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                is_inactive=is_inactive,
                flag_ids=list(a.flag_ids or []),
                permission_ids=list(a.permission_ids or []),
                agent_ids=list(agent_ids_by_tool.get(a.id, [])),
                department_ids=list(a.department_ids or []),
                updated_at=a.updated_at,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
            )
        )

    return rows
