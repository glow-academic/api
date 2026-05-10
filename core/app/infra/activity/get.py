"""Canonical shared activity get operations."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException

from app.infra.activity.context import (
    resolve_activity_context,
    resolve_activity_search_context,
)
from app.infra.activity.types import (
    ActivityHistoryResponse,
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
from app.infra.session.types import SessionListItem
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


async def _build_activity_history(
    pool,
    redis,
    request: ActivityRequest,
    *,
    bypass_cache: bool = False,
) -> ActivityHistoryResponse:
    ctx = await resolve_activity_search_context(
        pool,
        redis,
        department_ids=request.department_ids or None,
        role_ids=request.role_ids or None,
        date_from=request.date_from,
        date_to=request.date_to,
        sort_order=request.history_sort_order,
        page=request.history_page,
        page_size=request.history_page_size,
        bypass_cache=bypass_cache,
    )

    sessions = ctx.entries.get("sessions", [])
    total_sessions = ctx.entries.get("total_sessions", [])
    groups = ctx.entries.get("groups", [])
    runs = ctx.entries.get("runs", [])

    names_rp = ctx.resources.get("names")
    name_list = names_rp.selected if names_rp else []
    pricing_rp = ctx.resources.get("pricing")
    pricing_list = pricing_rp.selected if pricing_rp else []

    pricing_map: dict[UUID, dict] = {}
    for p in pricing_list:
        if p.id:
            pricing_map[p.id] = {
                "price": Decimal(str(p.price)) if p.price is not None else Decimal("0"),
                "unit_value": p.unit_value or 1,
            }

    name_map = {item.id: item.name for item in name_list if item.id and item.name}

    group_to_session: dict[UUID, UUID] = {}
    group_counts: dict[UUID, int] = defaultdict(int)
    for group in groups:
        if group.session_id:
            group_to_session[group.id] = group.session_id
            group_counts[group.session_id] += 1

    session_stats: dict[UUID, dict] = defaultdict(
        lambda: {
            "run_count": 0,
            "total_tokens": 0,
            "total_cost": Decimal("0"),
            "first_run_at": None,
            "last_run_at": None,
        }
    )

    for run in runs:
        session_id = group_to_session.get(run.group_id) if run.group_id else None
        if not session_id:
            continue
        stats = session_stats[session_id]
        stats["run_count"] += 1
        stats["total_tokens"] += (
            run.input_tokens + run.output_tokens + run.cached_input_tokens
        )

        run_cost = Decimal("0")
        for pricing in run.pricing:
            if pricing.pricing_id and pricing.count:
                info = pricing_map.get(pricing.pricing_id)
                if info and info["unit_value"] > 0:
                    run_cost += (
                        Decimal(str(pricing.count)) / Decimal(str(info["unit_value"]))
                    ) * info["price"]
        stats["total_cost"] += run_cost

        if run.run_created_at:
            if stats["first_run_at"] is None or run.run_created_at < stats["first_run_at"]:
                stats["first_run_at"] = run.run_created_at
            if stats["last_run_at"] is None or run.run_created_at > stats["last_run_at"]:
                stats["last_run_at"] = run.run_created_at

    items = [
        SessionListItem(
            session_id=session.id,
            profile_id=session.profile_id,
            profile_name=name_map.get(session.profile_id) if session.profile_id else None,
            session_created_at=session.created_at,
            active=session.active,
            group_count=group_counts.get(session.id, 0),
            run_count=session_stats.get(session.id, {}).get("run_count", 0),
            first_run_at=session_stats.get(session.id, {}).get("first_run_at"),
            last_run_at=session_stats.get(session.id, {}).get("last_run_at"),
            total_tokens=session_stats.get(session.id, {}).get("total_tokens", 0),
            total_cost=session_stats.get(session.id, {}).get(
                "total_cost", Decimal("0")
            ),
        )
        for session in sessions
    ]

    total_count = len(total_sessions)
    page_size = request.history_page_size
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
    return ActivityHistoryResponse(
        items=items,
        total_count=total_count,
        page=request.history_page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_activity_impl_cached(
    pool,
    request: ActivityRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/activity/get",
) -> tuple[ActivityResponse, bool]:
    tags = ["artifacts", "activity"]
    cache_key_val = cache_key(cache_key_path, request.model_dump(mode="json"))

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
    names_rp = ctx.resources.get("names")
    name_list = names_rp.selected if names_rp else []

    name_map: dict[UUID, str] = {
        item.id: item.name for item in name_list if item.id and item.name
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
        resources=ActivityResources(profiles={pid: {} for pid in profile_ids_set}),
        analytics=analytics_facets,
        history=await _build_activity_history(
            pool,
            redis,
            request,
            bypass_cache=bypass_cache,
        ),
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
