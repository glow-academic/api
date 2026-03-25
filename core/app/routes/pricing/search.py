"""Search endpoint for pricing artifact — group history, paginated."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.common_context import resolve_common_context
from app.infra.globals import get_pool, get_redis_client
from app.infra.pricing.context import resolve_pricing_search_context
from app.infra.pricing.types import (
    ListPricingRequest,
    ListPricingResponse,
    PricingGroupItem,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=ListPricingResponse)
async def search_pricing(
    request: ListPricingRequest,
    http_request: Request,
    response: Response,
) -> ListPricingResponse:
    """Get pricing group history (bottom table, paginated)."""
    tags = ["artifacts", "pricing", "list"]
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
            return ListPricingResponse.model_validate(cached["data"])

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
        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="Session ID is required.",
            )

        redis = get_redis_client()

        # --- Phase 0: Resolve common context (profile identity) ---
        common = await resolve_common_context(
            pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
        )
        if not common:
            raise HTTPException(status_code=401, detail="Profile not found")

        # --- Phase 1: Resolve pricing search context ---
        ctx = await resolve_pricing_search_context(
            pool,
            redis,
            session_ids=[session_id],
            date_from=request.effective_date_from,
            date_to=request.effective_date_to,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
            bypass_cache=bypass_cache,
        )

        # --- Phase 2: Extract data ---
        groups = ctx.entries.get("groups", [])
        total_groups = ctx.entries.get("total_groups", [])
        runs = ctx.entries.get("runs", [])

        pricing_rp = ctx.resources.get("pricing")
        pricing_list = pricing_rp.selected if pricing_rp else []
        names_rp = ctx.resources.get("names")
        name_list = names_rp.selected if names_rp else []

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

        # --- Phase 4: Aggregate runs per group ---
        group_stats: dict[UUID, dict] = defaultdict(
            lambda: {
                "run_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost": Decimal("0"),
                "first_run_at": None,
                "last_run_at": None,
                "agent_ids": set(),
                "model_ids": set(),
            }
        )

        for run in runs:
            gid = run.group_id
            if not gid:
                continue
            stats = group_stats[gid]
            stats["run_count"] += 1
            stats["total_input_tokens"] += run.input_tokens
            stats["total_output_tokens"] += run.output_tokens
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
            if run.agent_ids:
                stats["agent_ids"].update(run.agent_ids)
            if run.model_ids:
                stats["model_ids"].update(run.model_ids)

        # --- Phase 5: Build group items ---
        items: list[PricingGroupItem] = []
        for group in groups:
            gid = group.id
            stats = group_stats.get(gid, {})

            agent_id_list = list(stats.get("agent_ids", set()))
            model_id_list = list(stats.get("model_ids", set()))
            a_names = [
                name_map[aid] for aid in agent_id_list if aid in name_map
            ] or None
            m_names = [
                name_map[mid] for mid in model_id_list if mid in name_map
            ] or None

            items.append(
                PricingGroupItem(
                    group_id=gid,
                    session_id=group.session_id,
                    group_name=group.name,
                    first_run_at=stats.get("first_run_at"),
                    last_run_at=stats.get("last_run_at"),
                    run_count=stats.get("run_count", 0),
                    total_input_tokens=stats.get("total_input_tokens", 0),
                    total_output_tokens=stats.get("total_output_tokens", 0),
                    total_tokens=stats.get("total_tokens", 0),
                    total_cost=stats.get("total_cost", Decimal("0")),
                    agent_ids=agent_id_list or None,
                    model_ids=model_id_list or None,
                    agent_names=a_names,
                    model_names=m_names,
                )
            )

        total_count = len(total_groups)
        page_size = request.page_size
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        api_response = ListPricingResponse(
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
            operation="pricing_search",
            request=http_request,
        )
