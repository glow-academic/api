"""Canonical shared session get operations.

Two-layer BFF pattern:
- get_session_impl(): Core data fetcher via context resolver, returns SessionInternalData
- get_session (HTTP route): HTTP response layer with caching

Uses composable context resolver with black-box MV search tools.
Zero inline SQL — all data from context resolver + resource fetchers.
"""

import asyncio
from decimal import Decimal
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from app.infra.common_context import resolve_common_context
from app.infra.globals import get_redis_client
from app.infra.pricing import compute_costs_from_runs
from app.infra.session.context import resolve_session_context
from app.infra.tool_graph import score_tools
from app.infra.session.types import (
    ArtifactSessionGroup,
    GetSessionDetailResponse,
    SessionInternalData,
    SessionTimelineItem,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.models.get import get_models
from app.tools.resources.providers.get import get_providers
from app.tools.resources.systems.get import get_systems
from app.tools.resources.tools.get import get_tools
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

# Session entry types for tool scoring
SESSION_BUNDLE_ENTRIES: set[str] = {"problems"}


# =============================================================================
# Layer 1: Core data fetcher (context resolver → pure Python assembly)
# =============================================================================


async def get_session_impl(
    pool: asyncpg.Pool,
    profile_id: UUID,
    session_id: UUID,
    bypass_cache: bool = False,
) -> SessionInternalData:
    """Core session detail fetcher.

    Resolves session context (domain data) and common context (config chain)
    in parallel, then assembles SessionInternalData.
    """
    redis = get_redis_client()

    # Resolve common/profile context first so session queries can use the
    # canonical profiles_resource id expected by sessions_mv.
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )

    session_profile_id = (
        common.profile.profiles_id if common is not None else profile_id
    )

    ctx = await resolve_session_context(
        pool,
        redis,
        session_id=session_id,
        profile_id=session_profile_id,
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
        scores = score_tools(common.tool_graph, SESSION_BUNDLE_ENTRIES)
        resource_agent_ids = {
            target: (tool.agent_id if tool else None)
            for target, tool in scores.best.items()
        }
        resource_system_ids = {
            target: (tool.system_id if tool else None)
            for target, tool in scores.best.items()
        }

        # Hydrate config chain from tool_graph
        all_system_ids = list(
            dict.fromkeys(t.system_id for t in common.tool_graph.tools)
        )
        all_agent_ids = list(dict.fromkeys(t.agent_id for t in common.tool_graph.tools))
        all_tool_ids = list(dict.fromkeys(t.tool_id for t in common.tool_graph.tools))

        async def _fetch_systems() -> list:
            if not all_system_ids:
                return []
            async with pool.acquire() as c:
                return await get_systems(c, all_system_ids, redis, bypass_cache)

        async def _fetch_agents() -> list:
            if not all_agent_ids:
                return []
            async with pool.acquire() as c:
                return await get_agents(c, all_agent_ids, redis, bypass_cache)

        async def _fetch_tools_config() -> list:
            if not all_tool_ids:
                return []
            async with pool.acquire() as c:
                return await get_tools(c, all_tool_ids, redis, bypass_cache)

        config_systems, config_agents, config_tools = await asyncio.gather(
            _fetch_systems(),
            _fetch_agents(),
            _fetch_tools_config(),
        )

        # Walk agent → model → provider chain
        model_ids = list(dict.fromkeys(a.model_id for a in config_agents if a.model_id))
        if model_ids:
            async with pool.acquire() as c:
                config_models = await get_models(c, model_ids, redis, bypass_cache)

        provider_ids = list(
            dict.fromkeys(m.provider_id for m in config_models if m.provider_id)
        )
        if provider_ids:
            async with pool.acquire() as c:
                config_providers = await get_providers(
                    c, provider_ids, redis, bypass_cache
                )

        # Config profile
        if common.profile:
            from app.tools.resources.profiles.get import get_profiles

            async with pool.acquire() as c:
                config_profile = await get_profiles(
                    c, [common.profile.profiles_id], redis, bypass_cache
                )

        runs_today = common.runs if common.runs else None

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
    cache_key_path: str = "/v5/session/get",
) -> tuple[GetSessionDetailResponse, bool]:
    """Build the cached client-facing session detail response."""
    tags = ["artifacts", "session"]
    cache_key_val = cache_key(
        cache_key_path,
        {"session_id": str(session_id)},
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
