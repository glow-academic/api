"""Resolve group context — black-box tools only.

Group detail is a single-group view with runs, messages, and calls.
Uses groups_mv, runs_mv, messages_mv, calls_mv via MV search tools,
then hydrates resources (names, tools) for display.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.calls.search import search_calls
from app.tools.entries.groups.get import get_groups
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.search import search_runs
from app.tools.resources.names.get import get_names
from app.tools.resources.tools.get import get_tools


async def resolve_group_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    group_id: UUID,
    profile_id: UUID,
    bypass_cache: bool = False,
    message_limit: int | None = None,
    message_offset: int | None = None,
) -> ArtifactContext:
    """Resolve group context for get.py.

    Entries:
      - runs: runs_mv rows (all runs for group)
      - messages: messages_mv rows (all/paginated messages for runs)
      - calls: calls_mv rows (all calls for runs)
      - actor_name_items: name lookups for actor
      - group_name: group display name
      - group_created_at: group creation timestamp
      - session_id: group session ID
      - total_message_count: total messages (for pagination)

    Resources:
      - names: name lookups for agents, models, profiles
      - tools: tool resources for call template names
    """

    # ── Phase 1: Fetch runs + actor name + group info in parallel ────
    async def _fetch_runs() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_runs(
                c, group_ids=[group_id], sort_order="asc", limit=10000
            )
            return items

    async def _fetch_actor_name() -> list:
        async with pool.acquire() as c:
            return await get_names(c, [profile_id], redis, bypass_cache=bypass_cache)

    async def _fetch_group_info() -> list:
        async with pool.acquire() as c:
            return await get_groups(c, [group_id])

    runs, actor_name_items, group_info = await asyncio.gather(
        _fetch_runs(),
        _fetch_actor_name(),
        _fetch_group_info(),
    )

    group = group_info[0] if group_info else None

    if not runs:
        return _empty_context(profile_id, actor_name_items, group)

    # ── Phase 2: Fetch messages + calls for all runs (parallel) ──────
    run_ids = [r.run_id for r in runs]

    async def _fetch_messages() -> tuple[list, int]:
        async with pool.acquire() as c:
            return await search_messages(
                c,
                run_ids=run_ids,
                sort_order="asc",
                limit=message_limit or 100000,
                offset=message_offset or 0,
            )

    async def _fetch_calls() -> list:
        async with pool.acquire() as c:
            return await search_calls(c, run_ids=run_ids, limit=100000)

    (messages, total_message_count), calls = await asyncio.gather(
        _fetch_messages(),
        _fetch_calls(),
    )

    # ── Phase 3: Collect resource IDs ────────────────────────────────
    name_ids_set: set[UUID] = set()
    tool_ids_set: set[UUID] = set()

    for r in runs:
        if r.model_ids:
            name_ids_set.update(r.model_ids)
        if r.agent_ids:
            name_ids_set.update(r.agent_ids)

    for c in calls:
        if c.tool_id:
            tool_ids_set.add(c.tool_id)

    # ── Phase 4: Parallel resource hydration ─────────────────────────
    async def _get_names() -> list:
        if not name_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_names(
                c, list(name_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_tools() -> list:
        if not tool_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_tools(
                c, list(tool_ids_set), redis, bypass_cache=bypass_cache
            )

    names_res, tools_res = await asyncio.gather(
        _get_names(),
        _get_tools(),
    )

    # ── Phase 5: Return ArtifactContext ──────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=group_id,
        draft_version=None,
        entries={
            "runs": runs,
            "messages": messages,
            "calls": calls,
            "actor_name_items": actor_name_items,
            "group_name": group.name if group else None,
            "group_created_at": group.created_at if group else None,
            "session_id": group.session_id if group else None,
            "total_message_count": total_message_count,
        },
        resources={
            "names": ResourcePair(selected=names_res, suggestions=[]),
            "tools": ResourcePair(selected=tools_res, suggestions=[]),
        },
    )


def _empty_context(
    profile_id: UUID, actor_name_items: list, group: object | None = None
) -> ArtifactContext:
    """Return an empty ArtifactContext when group has no runs."""
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "runs": [],
            "messages": [],
            "calls": [],
            "actor_name_items": actor_name_items,
            "group_name": group.name if group else None,
            "group_created_at": group.created_at if group else None,
            "session_id": group.session_id if group else None,
            "total_message_count": 0,
        },
        resources={},
    )
