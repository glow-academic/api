"""Resolve activity context — raw MV reads + hydrated resources.

Activity is a dashboard endpoint with no artifact table and no drafts.
Two context resolvers:
  - resolve_activity_context: top cards (header metrics + profile summary)
  - resolve_activity_search_context: bottom table (session list, paginated)

Both pull from multiple MVs. Cost computation uses pricing_resource.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.dashboard.visibility import resolve_visible_profile_ids
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.types import ArtifactContext, ResourcePair

# Entry fetchers (raw MV reads)
from app.tools.entries.activity.search import search_activity
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grants.search import search_grants
from app.tools.entries.groups.search import search_groups
from app.tools.entries.logins.search import search_logins
from app.tools.entries.problems.search import search_problems
from app.tools.entries.runs.search import search_runs
from app.tools.entries.sessions.search import search_sessions

# Resource get fetchers
from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.profiles.get import get_profiles


async def _resolve_profile_ids(
    pool: asyncpg.Pool,
    department_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
) -> list[UUID] | None:
    """Resolve department_ids + role_ids to matching profile_ids."""
    if not department_ids and not role_ids:
        return None
    conditions: list[str] = []
    params: list = []
    idx = 1
    if department_ids:
        conditions.append(f"p.department_ids && ${idx}::uuid[]")
        params.append(department_ids)
        idx += 1
    if role_ids:
        conditions.append(f"p.role_id = ANY(${idx}::uuid[])")
        params.append(role_ids)
        idx += 1
    where = " AND ".join(conditions)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT p.id FROM profiles_resource p WHERE {where}", *params
        )
    return [row["id"] for row in rows]


async def _clamp_to_visible(
    pool: asyncpg.Pool,
    actor_profile: ProfileIdentityContext | None,
    effective_profile_ids: list[UUID] | None,
) -> list[UUID] | None:
    """Clamp the requested ``profile_ids`` filter to the actor's visible set.

    Mirrors the session-detail gate (``resolve_session_context`` →
    ``resolve_visible_profile_ids``, issue #144): the org-wide session/activity
    lists must never return another profile's sessions to a caller who could
    not view that profile's session detail.

    - When no ``actor_profile`` is supplied (internal/legacy callers), the
      behaviour is unchanged — the filter passes through untouched.
    - Super-admins (``role_level == 0``) resolve to the full org set, so the
      intersection is a no-op and they keep global reach.
    - When the caller supplies a ``profile_ids`` / department / role filter, we
      INTERSECT it with the visible set (a Dept-A instructor asking for a
      Dept-B profile gets an empty result, never a leak).
    - When NO filter is supplied, we default to the actor's full VISIBLE set
      (NOT ``None``, which the search tools treat as "all profiles").

    Returns a concrete list of visible profile_ids (possibly empty). Returning
    ``None`` is reserved for the no-actor passthrough path only.
    """
    if actor_profile is None:
        return effective_profile_ids
    visible = set(await resolve_visible_profile_ids(pool, actor_profile))
    if effective_profile_ids is None:
        return list(visible)
    return [pid for pid in effective_profile_ids if pid in visible]


async def resolve_activity_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    actor_profile: ProfileIdentityContext | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve activity context for top cards (header metrics + profile summary).

    Entries (raw MVs):
      - sessions, activity, logins, problems, grants, emulations

    Resources (hydrated from IDs derived from entries):
      - profiles (for profile display name lookup keyed on profile_id)
    """
    # Step 1: Resolve department/role filters to profile_ids
    filter_profile_ids = await _resolve_profile_ids(pool, department_ids, role_ids)

    # Merge with direct profile_ids filter, then CLAMP to the actor's visible
    # set so an empty/cross-scope filter cannot leak org-wide sessions (the
    # session-detail sibling gates the same way — issue #144).
    effective_profile_ids = await _clamp_to_visible(
        pool, actor_profile, profile_ids or filter_profile_ids
    )

    # Step 2: Parallel fetch all entry grains
    async def _fetch_sessions() -> list:
        async with pool.acquire() as c:
            return await search_sessions(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_activity() -> list:
        async with pool.acquire() as c:
            return await search_activity(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_logins() -> list:
        async with pool.acquire() as c:
            return await search_logins(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_problems() -> list:
        async with pool.acquire() as c:
            return await search_problems(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_grants() -> list:
        async with pool.acquire() as c:
            return await search_grants(c, redis, limit=100000)

    async def _fetch_emulations() -> list:
        async with pool.acquire() as c:
            return await search_emulations(c, redis, limit=100000)

    (
        sessions,
        activity,
        logins,
        problems,
        grants,
        emulations,
    ) = await asyncio.gather(
        _fetch_sessions(),
        _fetch_activity(),
        _fetch_logins(),
        _fetch_problems(),
        _fetch_grants(),
        _fetch_emulations(),
    )

    # Step 3: Collect profile IDs for name resolution
    all_profile_ids: set[UUID] = set()
    for s in sessions:
        if s.profile_id:
            all_profile_ids.add(s.profile_id)
    for a in activity:
        if a.profile_id:
            all_profile_ids.add(a.profile_id)
    for lg in logins:
        if lg.profile_id:
            all_profile_ids.add(lg.profile_id)
    for p in problems:
        if p.profile_id:
            all_profile_ids.add(p.profile_id)

    # Step 4: Hydrate profile names from the canonical profiles
    # black box. ``get_profiles`` queries ``profiles_resource WHERE
    # id = ANY(...)`` so the returned items' ``.id`` is the
    # profile_id readers key on. Previously this used ``get_names``
    # which queries ``names_resource`` (tools/agents/models
    # namespace) — that lookup never hit on profile_ids, so every
    # ``name_map.get(profile_id)`` came back ``None`` (blank
    # Profile column on the activity table).
    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        return await get_profiles(
            pool, list(all_profile_ids), redis, bypass_cache=bypass_cache
        )

    profiles_selected = await _fetch_profiles()

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        resources={
            "profiles": ResourcePair(selected=profiles_selected, suggestions=[]),
        },
        entries={
            "sessions": sessions,
            "activity": activity,
            "logins": logins,
            "problems": problems,
            "grants": grants,
            "emulations": emulations,
        },
    )


async def resolve_activity_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    actor_profile: ProfileIdentityContext | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    active: bool | None = None,
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 50,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve activity search context for bottom table (session list).

    Entries (raw MVs):
      - sessions: sessions_mv rows (paginated)
      - total_sessions: sessions_mv rows (all matching, for total_count)
      - groups: groups_mv rows (for sessions on current page)
      - runs: runs_mv rows (for groups, token/cost aggregation)

    Resources (hydrated from IDs derived from entries):
      - profiles (display name lookup keyed on profile_id),
        pricing (cost computation)
    """
    # Step 1: Resolve department/role filters, then CLAMP to the actor's
    # visible set (mirrors the session-detail gate, issue #144) so an
    # empty/cross-scope filter cannot leak org-wide sessions.
    filter_profile_ids = await _resolve_profile_ids(pool, department_ids, role_ids)
    effective_profile_ids = await _clamp_to_visible(
        pool, actor_profile, profile_ids or filter_profile_ids
    )

    page_offset = page * page_size

    # Step 2: Paginated sessions + total count
    async def _fetch_sessions_page() -> list:
        async with pool.acquire() as c:
            return await search_sessions(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                active=active,
                limit=page_size,
                offset=page_offset,
            )

    async def _fetch_sessions_total() -> list:
        async with pool.acquire() as c:
            return await search_sessions(
                c,
                redis, profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                active=active,
                limit=100000,
                offset=0,
            )

    sessions, total_sessions = await asyncio.gather(
        _fetch_sessions_page(),
        _fetch_sessions_total(),
    )

    # Step 3: Groups for current page sessions
    session_ids = [s.id for s in sessions]
    if session_ids:
        async with pool.acquire() as c:
            groups = await search_groups(c, redis, session_ids=session_ids, limit=100000)
        async with pool.acquire() as c:
            problems = await search_problems(
                c,
                redis, session_ids=session_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )
    else:
        groups = []
        problems = []

    # Step 4: Runs for those groups
    group_ids = [g.id for g in groups]
    if group_ids:
        async with pool.acquire() as c:
            runs = (await search_runs(c, redis, group_ids=group_ids, limit=100000))[0]
    else:
        runs = []

    # Step 5: Collect resource IDs
    profile_ids_set: set[UUID] = set()
    pricing_ids_set: set[UUID] = set()

    for s in sessions:
        if s.profile_id:
            profile_ids_set.add(s.profile_id)

    for run in runs:
        for p in run.pricing:
            if p.pricing_id:
                pricing_ids_set.add(p.pricing_id)

    # Step 6: Parallel hydrate resources. ``get_profiles`` is the
    # canonical profile_id → name fetcher (queries
    # ``profiles_resource``); ``get_names`` would silently return
    # empty here because profile_ids don't live in
    # ``names_resource``.
    async def _fetch_profiles_res() -> list:
        if not profile_ids_set:
            return []
        return await get_profiles(
            pool, list(profile_ids_set), redis, bypass_cache=bypass_cache
        )

    async def _fetch_pricing_res() -> list:
        if not pricing_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_pricing(c, list(pricing_ids_set), redis, bypass_cache)

    profiles_selected, pricing_selected = await asyncio.gather(
        _fetch_profiles_res(),
        _fetch_pricing_res(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        resources={
            "profiles": ResourcePair(selected=profiles_selected, suggestions=[]),
            "pricing": ResourcePair(selected=pricing_selected, suggestions=[]),
        },
        entries={
            "sessions": sessions,
            "total_sessions": total_sessions,
            "groups": groups,
            "runs": runs,
            "problems": problems,
        },
    )


async def _empty_list() -> list:
    return []
