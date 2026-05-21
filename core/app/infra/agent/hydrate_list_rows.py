"""Hydrate ``ListAgentApiAgent`` rows for a specific set of agent ids.

Used by create/update/duplicate impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_agent_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate resources
→ compute permissions), without the facet aggregation, pagination, or
big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.agent.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_list_can_edit,
)
from app.infra.agent.types import ListAgentApiAgent
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.agent.get import get_agents
from app.tools.resources.flags.get import get_flags
from app.tools.resources.models.get import get_models as get_models_resource
from app.tools.resources.names.get import get_names


async def hydrate_agent_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    agent_ids: list[UUID],
) -> list[ListAgentApiAgent]:
    """Return ``ListAgentApiAgent`` rows for the given agent ids.

    Mirrors ``_search_agent_build``'s row-hydration steps minus facets
    and pagination. ``active_settings_count`` is reported as 0 (the
    agent is brand-new or just edited; settings interaction count is
    server-side materialized and reconciles on next page-level search).
    """
    if not agent_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

    async with pool.acquire() as conn:
        artifacts = await get_agents(
            conn,
            agent_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            models=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="agent", artifact_ids=agent_ids,
            limit=len(agent_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_model_ids: set[UUID] = set()
    all_flag_ids: set[UUID] = set()
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        for mid in a.model_ids or []:
            all_model_ids.add(mid)
        for fid in a.flag_ids or []:
            all_flag_ids.add(fid)

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _models() -> list:
        if not all_model_ids:
            return []
        async with pool.acquire() as conn:
            return await get_models_resource(conn, list(all_model_ids), redis)

    async def _flags() -> list:
        if not all_flag_ids:
            return []
        return await get_flags(pool, list(all_flag_ids), redis)

    names_data, models_data, flag_rows_data = await asyncio.gather(
        _names(), _models(), _flags(),
    )

    name_map = {n.id: n for n in names_data}
    model_map: dict[UUID, tuple[str | None, str | None]] = {}
    for m in models_data:
        m_id = getattr(m, "id", None)
        if m_id:
            model_map[m_id] = (m.name, m.description)

    # Flag id -> (type, value) for per-row boolean derivation.
    flag_meta_map: dict[UUID, tuple[str | None, bool | None]] = {
        f.id: (getattr(f, "type", None), getattr(f, "value", None))
        for f in flag_rows_data
        if getattr(f, "id", None)
    }

    rows: list[ListAgentApiAgent] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        model_id = a.model_ids[0] if a.model_ids else None
        model_name = None
        model_description = None
        if model_id and model_id in model_map:
            model_name, model_description = model_map[model_id]

        is_inactive = not a.active
        is_mcp = False
        for fid in a.flag_ids or []:
            ftype, fvalue = flag_meta_map.get(fid, (None, None))
            if ftype == "mcp" and fvalue is True:
                is_mcp = True
                break

        can_edit_val = compute_list_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            agent_department_ids=dept_ids_str,
            active_settings_count=0,
        )
        can_delete_val = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            active_settings_count=0,
        )
        can_duplicate_val = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
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

    return rows
