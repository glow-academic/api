"""Canonical shared session get operations.

Two-layer BFF pattern:
- get_session_impl(): Core data fetcher via context resolver, returns SessionInternalData
- get_session (HTTP route): HTTP response layer with caching

Uses composable context resolver with black-box MV search tools.
Zero inline SQL — all data from context resolver + resource fetchers.
"""

from decimal import Decimal
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from app.infra.common_context import resolve_common_context
from app.infra.runs_context import resolve_runs_context
from app.infra.globals import get_redis_client
from app.infra.pricing import compute_costs_from_runs
from app.infra.session.context import resolve_session_context
from app.infra.server_timing import timed
from app.infra.session.types import (
    ArtifactSessionGroup,
    GetSessionDetailResponse,
    SessionInternalData,
    SessionTimelineItem,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

# =============================================================================
# Layer 1: Core data fetcher (context resolver → pure Python assembly)
# =============================================================================


async def get_session_impl(
    pool: asyncpg.Pool,
    profile_id: UUID,
    session_id: UUID,
    bypass_cache: bool = False,
    **_kwargs,
) -> SessionInternalData:
    """Core session detail fetcher.

    Resolves session context (domain data) and common context (config chain)
    in parallel, then assembles SessionInternalData.
    """
    redis = get_redis_client()

    # Resolve common/profile context first so session queries can use the
    # canonical profiles_resource id expected by sessions_mv.
    with timed("permissions"):
        common = await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            bypass_cache=bypass_cache,
        )

    session_profile_id = (
        common.profile.profiles_id if common is not None else profile_id
    )

    with timed("resolve_session"):
        ctx = await resolve_session_context(
            pool,
            redis,
            session_id=session_id,
            profile_id=session_profile_id,
            actor_profile=common.profile if common is not None else None,
            bypass_cache=bypass_cache,
        )

    # Extract domain entries from session context
    session = ctx.entries.get("session")
    groups = ctx.entries.get("groups", [])
    runs = ctx.entries.get("runs", [])
    logins = ctx.entries.get("logins", [])
    problems = ctx.entries.get("problems", [])
    chats = ctx.entries.get("chats", [])
    attempt_homes = ctx.entries.get("attempt_homes", [])
    practices = ctx.entries.get("practices", [])
    actor_name_items = ctx.entries.get("actor_name_items", [])
    actor_name = actor_name_items[0].name if actor_name_items else None

    if not session:
        return SessionInternalData(
            session_exists=False,
            actor_name=actor_name,
        )

    # Extract resource maps from session context
    names_rp = ctx.resources.get("names")
    names_list = names_rp.selected if names_rp else []
    name_map = {item.id: item.name for item in names_list if item.id and item.name}

    # Profile name from name_map
    profile_name = name_map.get(session.profile_id) if session.profile_id else None

    # Build config chain from common context (if available)
    config_agents: list = []
    config_models: list = []
    config_providers: list = []
    config_tools: list = []
    config_systems: list = []
    config_profile: list = []
    runs_today = None
    resource_agent_ids: dict[str, UUID | None] = {}
    resource_system_ids: dict[str, UUID | None] = {}

    if common:
        # Tool-graph scoring/config-chain decoration is dead weight — the
        # client always shows "AI generate" regardless and the actual agent
        # dispatch happens server-side in ``prepare_generation``. The config_*
        # and resource_*_ids maps below are no longer consumed by any caller,
        # so they stay empty (the tool_graph that fed them was removed from
        # CommonContext in the slim-down).

        # Config profile
        if common.profile:
            from app.tools.resources.profiles.get import get_profiles

            config_profile = await get_profiles(
                pool, [common.profile.profiles_id], redis, bypass_cache
            )

        # Direct call — runs is no longer carried on CommonContext.
        runs_today = await resolve_runs_context(
            pool, profile_id=common.profile.profiles_id,
        )

    return SessionInternalData(
        session_exists=True,
        session=session,
        groups=groups,
        runs=runs,
        logins=logins,
        problems=problems,
        chats=chats,
        attempt_homes=attempt_homes,
        practices=practices,
        config_agents=config_agents,
        config_models=config_models,
        config_providers=config_providers,
        config_tools=config_tools,
        config_systems=config_systems,
        config_profile=config_profile,
        runs_today=runs_today,
        resource_agent_ids=resource_agent_ids,
        resource_system_ids=resource_system_ids,
        group_id=None,
        actor_name=actor_name,
        profile_name=profile_name,
        name_map=name_map,
    )


async def get_session_detail_impl(
    pool: asyncpg.Pool,
    *,
    profile_id: UUID,
    session_id: UUID,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetSessionDetailResponse:
    """Build the client-facing session detail response."""
    data = await get_session_impl(
        pool=pool,
        profile_id=profile_id,
        session_id=session_id,
        bypass_cache=bypass_cache,
    )

    if not data.session_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    session = data.session

    async with pool.acquire() as conn:
        run_costs = await compute_costs_from_runs(conn, data.runs, bypass_cache)

    group_run_aggs: dict[UUID, dict] = {}
    for run in data.runs:
        gid = run.group_id
        if not gid:
            continue
        if gid not in group_run_aggs:
            group_run_aggs[gid] = {
                "run_count": 0,
                "total_tokens": 0,
                "total_cost": Decimal("0"),
                "first_run_at": None,
                "last_run_at": None,
            }
        agg = group_run_aggs[gid]
        agg["run_count"] += 1
        agg["total_tokens"] += (
            run.input_tokens + run.output_tokens + run.cached_input_tokens
        )
        agg["total_cost"] += run_costs.get(run.run_id, Decimal("0"))
        if run.run_created_at:
            if agg["first_run_at"] is None or run.run_created_at < agg["first_run_at"]:
                agg["first_run_at"] = run.run_created_at
            if agg["last_run_at"] is None or run.run_created_at > agg["last_run_at"]:
                agg["last_run_at"] = run.run_created_at

    groups = []
    for g in data.groups:
        agg = group_run_aggs.get(g.id, {})
        groups.append(
            ArtifactSessionGroup(
                group_id=g.id,
                group_name=g.name,
                first_run_at=agg.get("first_run_at"),
                last_run_at=agg.get("last_run_at"),
                run_count=agg.get("run_count", 0),
                total_tokens=agg.get("total_tokens", 0),
                total_cost=agg.get("total_cost", Decimal("0")),
            )
        )

    with timed("build"):
        timeline = _build_timeline(data)

    return GetSessionDetailResponse(
        actor_name=data.actor_name,
        session_exists=True,
        session_id=session.id,
        profile_id=session.profile_id,
        profile_name=data.profile_name,
        session_created_at=session.created_at,
        active=session.active,
        groups=groups,
        timeline=timeline,
    )


async def get_session_detail_impl_cached(
    pool: asyncpg.Pool,
    *,
    profile_id: UUID,
    session_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/session/get",
) -> tuple[GetSessionDetailResponse, bool]:
    """Build the cached client-facing session detail response."""
    tags = ["artifacts", "session"]
    # Scope the cache entry to the actor: the response is gated by the actor's
    # visible-profile set (issue #144), so a key shared across actors would let
    # a privileged actor's full-detail response be served to an unauthorized one
    # on a cache hit, bypassing the gate. Keying on profile_id keeps the gate
    # authoritative per actor.
    cache_key_val = cache_key(
        cache_key_path,
        {"session_id": str(session_id)},
        user_ctx=str(profile_id),
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return GetSessionDetailResponse.model_validate(cached["data"]), True

    api_response = await get_session_detail_impl(
        pool,
        profile_id=profile_id,
        session_id=session_id,
        bypass_cache=bypass_cache,
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=get_redis_client(),
    )

    return api_response, False


# =============================================================================
# Timeline Assembly (pure Python)
# =============================================================================


def _build_timeline(data: SessionInternalData) -> list[SessionTimelineItem]:
    """Merge all timeline source entries into a sorted list.

    Sources: groups, logins, problems, chats, attempt_homes, practices.
    Sorted by created_at ascending to match original SQL UNION ordering.
    """
    items: list[SessionTimelineItem] = []

    # Groups
    for g in data.groups:
        items.append(
            SessionTimelineItem(
                event_type="group",
                entity_id=g.id,
                entity_name=g.name,
                created_at=g.created_at,
            )
        )

    # Logins
    for login in data.logins:
        items.append(
            SessionTimelineItem(
                event_type="login",
                entity_id=login.id,
                created_at=login.created_at,
            )
        )

    # Problems
    for p in data.problems:
        items.append(
            SessionTimelineItem(
                event_type="problem",
                entity_id=p.id,
                entity_name=p.type,
                created_at=p.created_at,
                extra_1=p.message,
            )
        )

    # Chats (from chat_mv — returns dicts)
    for c in data.chats:
        chat_id = (
            c.get("chat_entry_id")
            if isinstance(c, dict)
            else getattr(c, "chat_entry_id", None)
        )
        chat_name = c.get("name") if isinstance(c, dict) else getattr(c, "name", None)
        chat_created = (
            c.get("created_at")
            if isinstance(c, dict)
            else getattr(c, "created_at", None)
        )
        items.append(
            SessionTimelineItem(
                event_type="chat",
                entity_id=chat_id,
                entity_name=chat_name,
                created_at=chat_created,
            )
        )

    # Attempt homes
    for ah in data.attempt_homes:
        items.append(
            SessionTimelineItem(
                event_type="attempt",
                entity_id=ah.attempt_id,
                created_at=ah.created_at,
            )
        )

    # Practices
    for pr in data.practices:
        items.append(
            SessionTimelineItem(
                event_type="practice",
                entity_id=pr.id,
                created_at=pr.created_at,
            )
        )

    # Sort by created_at ascending
    items.sort(key=lambda x: x.created_at or x.created_at, reverse=False)

    return items
