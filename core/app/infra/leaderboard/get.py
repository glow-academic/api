"""Canonical shared leaderboard get operations."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.api_types import FilterOption
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.common_context import resolve_common_context
from app.infra.globals import get_redis_client
from app.infra.leaderboard.context import resolve_leaderboard_search_context
from app.infra.leaderboard.permissions import (
    build_leaderboard_rows_v3,
    build_leaderboard_sections_v3,
)
from app.infra.leaderboard.types import (
    LeaderboardProfileResource,
    LeaderboardRequest,
    LeaderboardResources,
    LeaderboardResponse,
    LeaderboardScenarioResource,
    LeaderboardSimulationResource,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

LEADERBOARD_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=VISIBLE,
        roles=HIDDEN,
        attempts=VISIBLE,
    ),
    mv_source="profile_facts",
    attempt_options=["general", "practice", "archived"],
)


def _resolve_attempt_type_filter(simulation_filters: list[str] | None) -> str | None:
    """Map multi-select attempt filters to the single MV attempt_type filter."""
    selected = set(simulation_filters or [])
    has_general = "general" in selected
    has_practice = "practice" in selected
    if has_general == has_practice:
        return None
    return "practice" if has_practice else "general"


def _parse_filters(request: LeaderboardRequest) -> dict[str, Any]:
    parsed_start_date = (
        datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        if request.start_date
        else None
    )
    parsed_end_date = (
        datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))
        if request.end_date
        else None
    )

    cohort_ids_filter = (
        request.cohort_ids
        if request.cohort_ids
        else ([request.cohort_id] if request.cohort_id else None)
    )
    simulation_ids_filter = (
        request.simulation_ids
        if request.simulation_ids
        else ([request.simulation_id] if request.simulation_id else None)
    )

    is_archived = bool(
        request.simulation_filters and "archived" in request.simulation_filters
    )
    attempt_type = _resolve_attempt_type_filter(request.simulation_filters)

    return {
        "date_from": parsed_start_date.date() if parsed_start_date else None,
        "date_to": parsed_end_date.date() if parsed_end_date else None,
        "cohort_ids": cohort_ids_filter,
        "department_ids": request.department_ids,
        "simulation_ids": simulation_ids_filter,
        "scenario_ids": request.scenario_ids,
        "attempt_type": attempt_type,
        "is_archived": is_archived,
    }


async def get_leaderboard_impl_cached(
    pool,
    request: LeaderboardRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/leaderboard/get",
) -> tuple[LeaderboardResponse, bool]:
    tags = ["artifacts", "leaderboard"]
    # Scope the cache entry to the actor: the leaderboard bundle carries
    # per-actor analytics facets (dept/cohort scoped via ``common.profile``),
    # so the response varies per profile, but LeaderboardRequest carries no
    # actor identity — a key built from the request body alone collides across
    # all callers and one profile's scoped facets would be served to another
    # on a cache hit (same class as #191/#194). Key on the actor's profile_id.
    cache_key_val = cache_key(
        cache_key_path, request.model_dump(mode="json"), user_ctx=str(profile_id)
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return LeaderboardResponse.model_validate(cached["data"]), True

    redis = get_redis_client()
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    filters = _parse_filters(request)
    # Use the search context (richer — also hydrates simulations + scenarios)
    # so we can build sections AND rows from one pass.
    ctx, analytics_facets = await asyncio.gather(
        resolve_leaderboard_search_context(
            pool,
            redis,
            target_profile_id=request.target_profile_id,
            cohort_ids=filters["cohort_ids"],
            department_ids=filters["department_ids"],
            simulation_ids=filters["simulation_ids"],
            scenario_ids=filters["scenario_ids"],
            attempt_type=filters["attempt_type"],
            is_archived=filters["is_archived"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            sort_order=request.sort_order or "desc",
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=LEADERBOARD_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    attempt_chats = ctx.entries.get("attempt_chats", [])
    attempt_messages = ctx.entries.get("attempt_messages", [])
    profiles_rp = ctx.resources.get("profiles")
    profile_list = profiles_rp.selected if profiles_rp else []
    simulations_rp = ctx.resources.get("simulations")
    sim_list = simulations_rp.selected if simulations_rp else []
    scenarios_rp = ctx.resources.get("scenarios")
    scenario_list = scenarios_rp.selected if scenarios_rp else []

    profile_resources = {
        str(item.id): LeaderboardProfileResource(
            profile_id=str(item.id),
            name=item.name,
            role=None,
        )
        for item in profile_list
        if item.id is not None
    }
    simulation_resources = {
        str(item.id): LeaderboardSimulationResource(
            simulation_id=str(item.id),
            name=item.name,
            description=item.description,
        )
        for item in sim_list
        if item.id is not None
    }
    scenario_resources = {
        str(item.id): LeaderboardScenarioResource(
            scenario_id=str(item.id),
            name=item.name,
            description=item.description,
        )
        for item in scenario_list
        if item.id is not None
    }

    resources = LeaderboardResources(
        profiles=profile_resources,
        simulations=simulation_resources,
        scenarios=scenario_resources,
    )

    # Build inline top-25% rows (replaces the deleted /search endpoint).
    profile_name_by_id: dict[str, str | None] = {
        pid: r.name for pid, r in profile_resources.items()
    }
    all_rows = build_leaderboard_rows_v3(
        attempt_chats=attempt_chats,
        attempt_messages=attempt_messages,
        profile_name_by_id=profile_name_by_id,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        rank_offset=0,
    )

    # Build filter options from the full-corpus resources (consumers in Pass 3
    # prefer these over page-derived).
    simulation_options = [
        FilterOption(value=sid, label=simulation_resources[sid].name)
        for sid in simulation_resources
        if simulation_resources[sid].name
    ]
    profile_options = [
        FilterOption(value=pid, label=profile_resources[pid].name)
        for pid in profile_resources
        if profile_resources[pid].name
    ]
    if request.search:
        q = request.search.lower()
        profile_options = [
            o for o in profile_options if q in (o.label or "").lower()
        ]

    api_response = LeaderboardResponse(
        sections=build_leaderboard_sections_v3(
            attempt_chats=attempt_chats,
            attempt_messages=attempt_messages,
        ),
        resources=resources,
        analytics=analytics_facets,
        data=all_rows,
        total_count=len(all_rows),
        simulation_options=simulation_options,
        profile_options=profile_options,
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return api_response, False


async def get_leaderboard_impl(
    pool,
    redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
    **filters,
) -> "LeaderboardResponse":
    """Canonical kwargs entry point — wraps ``get_leaderboard_impl_cached``."""
    from app.infra.leaderboard.types import LeaderboardRequest

    request = LeaderboardRequest(**filters)
    api_response, _cache_hit = await get_leaderboard_impl_cached(
        pool,
        request,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
        cache_key_path="/leaderboard/get",
    )
    return api_response
