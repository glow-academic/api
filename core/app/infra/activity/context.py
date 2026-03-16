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
from app.tools.resources.names.get import get_names
from app.tools.resources.pricing.get import get_pricing


async def _resolve_profile_ids(
    pool: asyncpg.Pool,
    department_ids: list[str] | None = None,
    roles: list[str] | None = None,
) -> list[UUID] | None:
    """Resolve department_ids + roles to matching profile_ids."""
    if not department_ids and not roles:
        return None
    conditions: list[str] = []
    params: list = []
    idx = 1
    if department_ids:
        conditions.append(f"p.department_ids && ${idx}::uuid[]")
        params.append([UUID(d) for d in department_ids])
        idx += 1
    if roles:
        conditions.append(f"""EXISTS (
            SELECT 1 FROM profile_roles_junction prj
            JOIN roles_resource r ON prj.role_id = r.id
            WHERE prj.profile_id = p.id AND prj.active = true
              AND r.role = ANY(${idx}::profile_type[])
        )""")
        params.append(roles)
        idx += 1
    where = " AND ".join(conditions)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT p.id FROM profiles_resource p WHERE {where}", *params
        )
    return [row["id"] for row in rows]


async def resolve_activity_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[str] | None = None,
    roles: list[str] | None = None,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve activity context for top cards (header metrics + profile summary).

    Entries (raw MVs):
      - sessions, activity, logins, problems, grants, emulations

    Resources (hydrated from IDs derived from entries):
      - names (for profile display)
    """
    # Step 1: Resolve department/role filters to profile_ids
    filter_profile_ids = await _resolve_profile_ids(pool, department_ids, roles)

    # Merge with direct profile_ids filter
    effective_profile_ids = profile_ids or filter_profile_ids

    # Step 2: Parallel fetch all entry grains
    async def _fetch_sessions() -> list:
        async with pool.acquire() as c:
            return await search_sessions(
                c,
                profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_activity() -> list:
        async with pool.acquire() as c:
            return await search_activity(
                c,
                profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_logins() -> list:
        async with pool.acquire() as c:
            return await search_logins(
                c,
                profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_problems() -> list:
        async with pool.acquire() as c:
            return await search_problems(
                c,
                profile_ids=effective_profile_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )

    async def _fetch_grants() -> list:
        async with pool.acquire() as c:
            return await search_grants(c, limit=100000)

    async def _fetch_emulations() -> list:
        async with pool.acquire() as c:
            return await search_emulations(c, limit=100000)

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

    # Step 4: Hydrate resources
    async def _fetch_names() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as c:
            return await get_names(
                c, list(all_profile_ids), redis, bypass_cache=bypass_cache
            )

    names_selected = await _fetch_names()

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=[]),
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
    department_ids: list[str] | None = None,
    roles: list[str] | None = None,
    profile_ids: list[UUID] | None = None,
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
      - names (profile display), pricing (cost computation)
    """
    # Step 1: Resolve department/role filters
    filter_profile_ids = await _resolve_profile_ids(pool, department_ids, roles)
    effective_profile_ids = profile_ids or filter_profile_ids

    page_offset = page * page_size

    # Step 2: Paginated sessions + total count
    async def _fetch_sessions_page() -> list:
        async with pool.acquire() as c:
            return await search_sessions(
                c,
                profile_ids=effective_profile_ids,
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
                profile_ids=effective_profile_ids,
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
            groups = await search_groups(c, session_ids=session_ids, limit=100000)
    else:
        groups = []

    # Step 4: Runs for those groups
    group_ids = [g.id for g in groups]
    if group_ids:
        async with pool.acquire() as c:
            runs = (await search_runs(c, group_ids=group_ids, limit=100000))[0]
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

    # Step 6: Parallel hydrate resources
    async def _fetch_names_res() -> list:
        if not profile_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_names(
                c, list(profile_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _fetch_pricing_res() -> list:
        if not pricing_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_pricing(c, list(pricing_ids_set), redis, bypass_cache)

    names_selected, pricing_selected = await asyncio.gather(
        _fetch_names_res(),
        _fetch_pricing_res(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=[]),
            "pricing": ResourcePair(selected=pricing_selected, suggestions=[]),
        },
        entries={
            "sessions": sessions,
            "total_sessions": total_sessions,
            "groups": groups,
            "runs": runs,
        },
    )


async def _empty_list() -> list:
    return []
