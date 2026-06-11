"""Canonical shared activity get operations."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException

from app.infra.activity.context import (
    resolve_activity_context,
)
from app.infra.activity.types import (
    ActivityProblemItem,
    ActivityRequest,
    ActivityResources,
    ActivityResponse,
    ProfileSummaryItem,
)
from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.common_context import resolve_common_context
from app.infra.globals import get_redis_client
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

ACTIVITY_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=HIDDEN,
        roles=HIDDEN,
        attempts=HIDDEN,
    ),
    mv_source="profile_facts",
)


def _build_profile_summary(
    sessions: list,
    activity: list,
    logins: list,
    problems: list,
    grants: list,
    name_map: dict[UUID, str],
) -> list[ProfileSummaryItem]:
    session_to_profile: dict[UUID, UUID] = {}
    for s in sessions:
        if s.id and s.profile_id:
            session_to_profile[s.id] = s.profile_id

    stats: dict[UUID, dict] = defaultdict(
        lambda: {
            "sessions_count": 0,
            "logins_count": 0,
            "grants_count": 0,
            "problems_count": 0,
            "activity_count": 0,
        }
    )

    for s in sessions:
        if s.profile_id:
            stats[s.profile_id]["sessions_count"] += 1
    for a in activity:
        if a.profile_id:
            stats[a.profile_id]["activity_count"] += 1
    for lg in logins:
        if lg.profile_id:
            stats[lg.profile_id]["logins_count"] += 1
    for p in problems:
        if p.profile_id:
            stats[p.profile_id]["problems_count"] += 1
    for g in grants:
        pid = session_to_profile.get(g.session_id) if g.session_id else None
        if pid:
            stats[pid]["grants_count"] += 1

    return [
        ProfileSummaryItem(
            profile_id=pid,
            profile_name=name_map.get(pid),
            sessions_count=s["sessions_count"],
            logins_count=s["logins_count"],
            grants_count=s["grants_count"],
            problems_count=s["problems_count"],
            activity_count=s["activity_count"],
        )
        for pid, s in stats.items()
    ]



async def get_activity_impl_cached(
    pool,
    request: ActivityRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/activity/get",
) -> tuple[ActivityResponse, bool]:
    tags = ["artifacts", "activity"]
    # Scope the cache entry to the actor: the activity bundle carries
    # per-actor analytics facets (dept scoped via ``common.profile``), so the
    # response varies per profile, but ActivityRequest carries no actor
    # identity — a key built from the request body alone collides across all
    # callers and one profile's scoped facets would be served to another on a
    # cache hit (same class as #191/#194). Key on the actor's profile_id.
    cache_key_val = cache_key(
        cache_key_path, request.model_dump(mode="json"), user_ctx=str(profile_id)
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return ActivityResponse.model_validate(cached["data"]), True

    redis = get_redis_client()
    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    ctx, analytics_facets = await asyncio.gather(
        resolve_activity_context(
            pool,
            redis,
            department_ids=request.department_ids or None,
            role_ids=request.role_ids or None,
            actor_profile=common.profile,
            date_from=request.date_from,
            date_to=request.date_to,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=ACTIVITY_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    sessions = ctx.entries.get("sessions", [])
    activity = ctx.entries.get("activity", [])
    logins = ctx.entries.get("logins", [])
    problems = ctx.entries.get("problems", [])
    grants = ctx.entries.get("grants", [])
    emulations = ctx.entries.get("emulations", [])
    profiles_rp = ctx.resources.get("profiles")
    profile_list = profiles_rp.selected if profiles_rp else []

    # Map profile_id → display name. ``profiles_rp.selected`` items
    # come from ``profiles_resource`` (via ``get_profiles``) so
    # ``.id`` is the profile_id readers key on.
    name_map: dict[UUID, str] = {
        item.id: item.name for item in profile_list if item.id and item.name
    }

    profile_summary = _build_profile_summary(
        sessions,
        activity,
        logins,
        problems,
        grants,
        name_map,
    )
    if request.summary_profile_id:
        profile_summary = [
            item
            for item in profile_summary
            if item.profile_id == request.summary_profile_id
        ]

    problem_items = [
        ActivityProblemItem(
            problem_id=p.id,
            profile_id=p.profile_id,
            profile_name=name_map.get(p.profile_id) if p.profile_id else None,
            session_id=p.session_id,
            type=p.type,
            message=p.message,
            resolved=p.resolved,
            created_at=p.created_at,
        )
        for p in problems[:50]
    ]

    profile_ids_set: set[str] = set()
    for s in sessions:
        if s.profile_id:
            profile_ids_set.add(str(s.profile_id))
    for lg in logins:
        if lg.profile_id:
            profile_ids_set.add(str(lg.profile_id))

    api_response = ActivityResponse(
        sessions_count=len(sessions),
        active_profiles_count=len({a.profile_id for a in activity if a.profile_id}),
        logins_count=len(logins),
        emulations_count=len(emulations),
        profile_summary=profile_summary,
        problems=problem_items,
        resources=ActivityResources(profiles={pid: {} for pid in profile_ids_set}),
        analytics=analytics_facets,
        # `history` is intentionally None — paginated sessions list now lives
        # at /system/sessions. Field retained on ActivityResponse for
        # prop-shape compatibility with clients that merge results in.
        history=None,
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return api_response, False


async def get_activity_impl(
    pool,
    redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    date_from=None,
    date_to=None,
    department_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> ActivityResponse:
    """Canonical kwargs entry point — wraps ``get_activity_impl_cached``.

    Exists so ``execute_infra_operation`` can dispatch this dashboard via
    the standard ``(pool, redis, *, profile_id, ...) -> Response`` shape.
    """
    request = ActivityRequest(
        date_from=date_from,
        date_to=date_to,
        department_ids=department_ids or [],
        role_ids=role_ids or [],
    )
    response_data, _cache_hit = await get_activity_impl_cached(
        pool,
        request,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
        cache_key_path="/activity/get",
    )
    return response_data
