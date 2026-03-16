"""Resolve session context — black-box tools only.

Session detail is a single-session view with groups, runs, and timeline events.
Uses sessions_mv, groups_mv, runs_mv, logins_mv, problems_mv, chat_mv,
attempt_home_mv, practice_mv via MV search tools, then hydrates resources
(names) for display.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.attempt_home.search import search_attempt_homes
from app.tools.entries.chat.search import search_chat_entries_internal
from app.tools.entries.groups.search import search_groups
from app.tools.entries.logins.search import search_logins
from app.tools.entries.practice.search import search_practices
from app.tools.entries.problems.search import search_problems
from app.tools.entries.runs.search import search_runs
from app.tools.entries.sessions.search import search_sessions
from app.tools.resources.names.get import get_names


async def resolve_session_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    session_id: UUID,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve session context for get.py.

    Entries:
      - sessions: session record (verify existence)
      - groups: groups_mv rows for session
      - runs: runs_mv rows for all groups
      - logins: logins_mv rows for session (timeline)
      - problems: problems_mv rows for session (timeline)
      - chats: chat_mv rows for session (timeline)
      - attempt_homes: attempt_home_mv rows for session (timeline)
      - practices: practice_mv rows for session (timeline)
      - actor_name_items: profile name for actor context

    Resources:
      - names: name lookups for profiles
    """

    # ── Phase 1: Fetch session + groups + actor name in parallel ───
    async def _fetch_sessions() -> list:
        async with pool.acquire() as c:
            return await search_sessions(c, profile_ids=[profile_id], limit=10000)

    async def _fetch_groups() -> list:
        async with pool.acquire() as c:
            return await search_groups(c, session_ids=[session_id], limit=10000)

    async def _fetch_actor_name() -> list:
        async with pool.acquire() as c:
            return await get_names(c, [profile_id], redis, bypass_cache=bypass_cache)

    sessions, groups, actor_name_items = await asyncio.gather(
        _fetch_sessions(),
        _fetch_groups(),
        _fetch_actor_name(),
    )

    # Find the specific session
    session = next((s for s in sessions if s.id == session_id), None)
    if not session:
        return _empty_context(actor_name_items)

    # ── Phase 2: Fetch runs + timeline entries in parallel ─────────
    group_ids = [g.id for g in groups]

    async def _fetch_runs() -> list:
        if not group_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_runs(
                c, group_ids=group_ids, sort_order="asc", limit=100000
            )
            return items

    async def _fetch_logins() -> list:
        async with pool.acquire() as c:
            return await search_logins(c, session_ids=[session_id], limit=100000)

    async def _fetch_problems() -> list:
        async with pool.acquire() as c:
            return await search_problems(c, session_ids=[session_id], limit=100000)

    async def _fetch_chats() -> list:
        async with pool.acquire() as c:
            return await search_chat_entries_internal(
                c, session_ids=[session_id], limit_count=100000
            )

    async def _fetch_attempt_homes() -> list:
        async with pool.acquire() as c:
            return await search_attempt_homes(c, session_ids=[session_id], limit=100000)

    async def _fetch_practices() -> list:
        async with pool.acquire() as c:
            return await search_practices(c, session_ids=[session_id], limit=100000)

    runs, logins, problems, chats, attempt_homes, practices = await asyncio.gather(
        _fetch_runs(),
        _fetch_logins(),
        _fetch_problems(),
        _fetch_chats(),
        _fetch_attempt_homes(),
        _fetch_practices(),
    )

    # ── Phase 3: Collect resource IDs ──────────────────────────────
    name_ids_set: set[UUID] = set()
    if session.profile_id:
        name_ids_set.add(session.profile_id)

    # ── Phase 4: Parallel resource hydration ───────────────────────
    async def _get_names() -> list:
        if not name_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_names(
                c, list(name_ids_set), redis, bypass_cache=bypass_cache
            )

    names_res = await _get_names()

    # ── Phase 5: Return ArtifactContext ────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=session.active,
        group_id=None,
        draft_version=None,
        entries={
            "session": session,
            "groups": groups,
            "runs": runs,
            "logins": logins,
            "problems": problems,
            "chats": chats,
            "attempt_homes": attempt_homes,
            "practices": practices,
            "actor_name_items": actor_name_items,
        },
        resources={
            "names": ResourcePair(selected=names_res, suggestions=[]),
        },
    )


def _empty_context(actor_name_items: list) -> ArtifactContext:
    """Return an empty ArtifactContext when session not found."""
    return ArtifactContext(
        artifact_id=None,
        active=False,
        group_id=None,
        draft_version=None,
        entries={
            "session": None,
            "groups": [],
            "runs": [],
            "logins": [],
            "problems": [],
            "chats": [],
            "attempt_homes": [],
            "practices": [],
            "actor_name_items": actor_name_items,
        },
        resources={},
    )
