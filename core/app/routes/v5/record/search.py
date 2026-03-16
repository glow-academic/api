"""Record artifact — search endpoint (attempt history for one profile, paginated).

Composable pattern: resolve_common_context → resolve_dashboard_search_context → Python assembly.
Reuses dashboard's _build_history_response for pure Python assembly.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.common_context import resolve_common_context
from app.infra.dashboard.context import resolve_dashboard_search_context
from app.infra.globals import get_pool, get_redis_client
from app.routes.v5.dashboard.search import _build_history_response
from app.infra.record.types import ListRecordRequest
from app.infra.v5_types import HistoryResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=HistoryResponse)
async def search_record(
    request: ListRecordRequest,
    http_request: Request,
    response: Response,
) -> HistoryResponse:
    """Get record attempt history for a single profile (paginated)."""
    tags = ["artifacts", "record", "list"]
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
            return HistoryResponse.model_validate(cached["data"])

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

        # --- Phase 0: Resolve common context ---
        async with pool.acquire() as c:
            common = await resolve_common_context(
                c, redis, profile_id=profile_id, bypass_cache=bypass_cache
            )
        if not common:
            raise HTTPException(status_code=401, detail="Profile not found")

        # Resolve profile_resource_id
        async with pool.acquire() as c:
            profile_resource_id: UUID | None = await c.fetchval(
                """
                SELECT profiles_id FROM profile_profiles_junction
                WHERE profile_id = $1 AND active = true
                LIMIT 1
                """,
                profile_id,
            )

        # Parse dates
        date_from = None
        date_to = None
        if request.start_date:
            date_from = datetime.fromisoformat(
                request.start_date.replace("Z", "+00:00")
            ).date()
        if request.end_date:
            date_to = datetime.fromisoformat(
                request.end_date.replace("Z", "+00:00")
            ).date()

        # --- Phase 1: Resolve dashboard search context (scoped to target profile) ---
        ctx = await resolve_dashboard_search_context(
            pool,
            redis,
            profile_resource_id=profile_resource_id,
            target_profile_id=request.target_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=request.department_ids,
            practice=request.practice,
            scenario_ids=request.scenario_ids,
            infinite_mode=request.infinite_mode,
            show_archived=request.show_archived,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache,
        )

        # --- Phase 2: Pure Python assembly ---
        api_response = _build_history_response(
            ctx,
            practice=request.practice,
            simulation_search=request.simulation_search,
            scenario_search=request.scenario_search,
            page=request.page,
            page_size=request.page_size,
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
            operation="record_search",
            request=http_request,
        )
