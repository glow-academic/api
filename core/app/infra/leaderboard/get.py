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
from app.infra.common_context import resolve_common_context
from app.infra.globals import get_redis_client
from app.infra.leaderboard.context import resolve_leaderboard_context
from app.infra.leaderboard.permissions import build_leaderboard_sections_v3
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.leaderboard.types import (
    LeaderboardProfileResource,
    LeaderboardRequest,
    LeaderboardResources,
    LeaderboardResponse,
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

    is_archived = bool(
        request.simulation_filters and "archived" in request.simulation_filters
    )
    if request.simulation_filters and "practice" in request.simulation_filters:
        attempt_type = "practice"
    else:
        attempt_type = "general"

    return {
        "date_from": parsed_start_date.date() if parsed_start_date else None,
        "date_to": parsed_end_date.date() if parsed_end_date else None,
        "cohort_ids": cohort_ids_filter,
        "department_ids": request.department_ids,
        "attempt_type": attempt_type,
        "is_archived": is_archived,
    }


async def get_leaderboard_impl_cached(
    pool,
    request: LeaderboardRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/v5/leaderboard/get",
) -> tuple[LeaderboardResponse, bool]:
    tags = ["artifacts", "leaderboard"]
    cache_key_val = cache_key(cache_key_path, request.model_dump(mode="json"))

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
    ctx, analytics_facets = await asyncio.gather(
        resolve_leaderboard_context(
            pool,
            redis,
            target_profile_id=request.target_profile_id,
            cohort_ids=filters["cohort_ids"],
            department_ids=filters["department_ids"],
            attempt_type=filters["attempt_type"],
            is_archived=filters["is_archived"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
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

    resources = LeaderboardResources(
        profiles={
            str(item.id): LeaderboardProfileResource(
                profile_id=str(item.id),
                name=item.name,
                role=None,
            )
            for item in profile_list
            if item.id is not None
        }
    )

    api_response = LeaderboardResponse(
        sections=build_leaderboard_sections_v3(
            attempt_chats=attempt_chats,
            attempt_messages=attempt_messages,
        ),
        resources=resources,
        analytics=analytics_facets,
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return api_response, False
