"""Search endpoint for activity artifact — session history, paginated."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.activity.context import resolve_activity_search_context
from app.infra.common_context import resolve_common_context
from app.infra.globals import get_pool, get_redis_client
from app.infra.activity.types import (
    ListActivityRequest,
    ListActivityResponse,
)
from app.infra.session.types import SessionListItem
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=ListActivityResponse)
async def search_activity(
    request: ListActivityRequest,
    http_request: Request,
    response: Response,
) -> ListActivityResponse:
    """Get activity session history (bottom table, paginated)."""
    tags = ["artifacts", "activity", "list"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    cache_key_val = cache_key(
        http_request.url.path,
        request.model_dump(mode="json"),
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            response.headers["X-Cache-Tags"] = ",".join(tags)
            response.headers["X-Cache-Hit"] = "1"
            return ListActivityResponse.model_validate(cached["data"])

    try:
        pool = get_pool()
        if not pool:
            raise RuntimeError("Database pool not initialized")

        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        redis = get_redis_client()

        # --- Phase 0: Resolve common context (profile identity) ---
        common = await resolve_common_context(
            pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
        )
        if not common:
            raise HTTPException(status_code=401, detail="Profile not found")

        # --- Phase 1: Resolve activity search context ---
        ctx = await resolve_activity_search_context(
            pool,
            redis,
            department_ids=request.department_ids or None,
            roles=request.roles or None,
            date_from=request.date_from,
            date_to=request.date_to,
            active=request.active,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
            bypass_cache=bypass_cache,
        )

        # --- Phase 2: Extract data ---
        sessions = ctx.entries.get("sessions", [])
        total_sessions = ctx.entries.get("total_sessions", [])
        groups = ctx.entries.get("groups", [])
        runs = ctx.entries.get("runs", [])

        names_rp = ctx.resources.get("names")
        name_list = names_rp.selected if names_rp else []
        pricing_rp = ctx.resources.get("pricing")
        pricing_list = pricing_rp.selected if pricing_rp else []

        # --- Phase 3: Build pricing map + name map ---
        pricing_map: dict[UUID, dict] = {}
        for p in pricing_list:
            if p.id:
                pricing_map[p.id] = {
                    "price": Decimal(str(p.price))
                    if p.price is not None
                    else Decimal("0"),
                    "unit_value": p.unit_value or 1,
                }

        name_map = {item.id: item.name for item in name_list if item.id and item.name}

        # --- Phase 4: Build group_id → session_id mapping ---
        group_to_session: dict[UUID, UUID] = {}
        group_counts: dict[UUID, int] = defaultdict(int)
        for g in groups:
            if g.session_id:
                group_to_session[g.id] = g.session_id
                group_counts[g.session_id] += 1

        # --- Phase 5: Aggregate run stats per session ---
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
            sid = group_to_session.get(run.group_id) if run.group_id else None
            if not sid:
                continue
            stats = session_stats[sid]
            stats["run_count"] += 1
            stats["total_tokens"] += (
                run.input_tokens + run.output_tokens + run.cached_input_tokens
            )

            # Compute cost inline
            run_cost = Decimal("0")
            for p in run.pricing:
                if p.pricing_id and p.count:
                    info = pricing_map.get(p.pricing_id)
                    if info and info["unit_value"] > 0:
                        run_cost += (
                            Decimal(str(p.count)) / Decimal(str(info["unit_value"]))
                        ) * info["price"]
            stats["total_cost"] += run_cost

            if run.run_created_at:
                if (
                    stats["first_run_at"] is None
                    or run.run_created_at < stats["first_run_at"]
                ):
                    stats["first_run_at"] = run.run_created_at
                if (
                    stats["last_run_at"] is None
                    or run.run_created_at > stats["last_run_at"]
                ):
                    stats["last_run_at"] = run.run_created_at

        # --- Phase 6: Build session items ---
        items: list[SessionListItem] = []
        for session in sessions:
            sid = session.id
            stats = session_stats.get(sid, {})

            items.append(
                SessionListItem(
                    session_id=sid,
                    profile_id=session.profile_id,
                    profile_name=name_map.get(session.profile_id)
                    if session.profile_id
                    else None,
                    session_created_at=session.created_at,
                    active=session.active,
                    group_count=group_counts.get(sid, 0),
                    run_count=stats.get("run_count", 0),
                    first_run_at=stats.get("first_run_at"),
                    last_run_at=stats.get("last_run_at"),
                    total_tokens=stats.get("total_tokens", 0),
                    total_cost=stats.get("total_cost", Decimal("0")),
                )
            )

        total_count = len(total_sessions)
        page_size = request.page_size
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        api_response = ListActivityResponse(
            data=items,
            total_count=total_count,
            page=request.page,
            page_size=page_size,
            total_pages=total_pages,
        )

        await set_cached(
            cache_key_val,
            {"data": api_response.model_dump(mode="json")},
            ttl=300,
            tags=tags,
            redis=redis,
        )
        response.headers["X-Cache-Tags"] = ",".join(tags)
        response.headers["X-Cache-Hit"] = "0"

        return api_response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="activity_search",
            request=http_request,
        )
