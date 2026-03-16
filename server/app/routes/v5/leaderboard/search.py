"""Search endpoint for leaderboard artifact — profile rows, paginated."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.common_context import resolve_common_context
from app.infra.globals import get_pool, get_redis_client
from app.infra.leaderboard.context import resolve_leaderboard_search_context
from app.infra.leaderboard.permissions import (
    build_leaderboard_rows_v3,
)
from app.infra.leaderboard.types import (
    LeaderboardProfileResource,
    LeaderboardResources,
    LeaderboardScenarioResource,
    LeaderboardSimulationResource,
    ListLeaderboardRequest,
    ListLeaderboardResponse,
)
from app.infra.v5_types import FilterOption
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=ListLeaderboardResponse)
async def search_leaderboard(
    request: ListLeaderboardRequest,
    http_request: Request,
    response: Response,
) -> ListLeaderboardResponse:
    """Get leaderboard profile rows (bottom table, paginated)."""
    tags = ["artifacts", "leaderboard", "list"]
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
            return ListLeaderboardResponse.model_validate(cached["data"])

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

        # --- Phase 1: Parse filters ---
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

        simulation_ids_filter = (
            request.simulation_ids
            if request.simulation_ids
            else ([request.simulation_id] if request.simulation_id else None)
        )
        cohort_ids_filter = (
            request.cohort_ids
            if request.cohort_ids
            else ([request.cohort_id] if request.cohort_id else None)
        )

        is_archived = bool(
            request.simulation_filters and "archived" in request.simulation_filters
        )
        if request.simulation_filters and "general" in request.simulation_filters:
            attempt_type = "general"
        elif request.simulation_filters and "practice" in request.simulation_filters:
            attempt_type = "practice"
        else:
            attempt_type = "general"

        # --- Phase 2: Resolve leaderboard search context ---
        ctx = await resolve_leaderboard_search_context(
            pool,
            redis,
            target_profile_id=request.target_profile_id,
            cohort_ids=cohort_ids_filter,
            department_ids=request.department_ids,
            simulation_ids=simulation_ids_filter,
            scenario_ids=request.scenario_ids,
            attempt_type=attempt_type,
            is_archived=is_archived,
            date_from=parsed_start_date.date() if parsed_start_date else None,
            date_to=parsed_end_date.date() if parsed_end_date else None,
            sort_order=request.sort_order or "desc",
            bypass_cache=bypass_cache,
        )

        # --- Phase 3: Extract data ---
        attempt_chats = ctx.entries.get("attempt_chats", [])
        attempt_messages = ctx.entries.get("attempt_messages", [])

        profiles_rp = ctx.resources.get("profiles")
        profile_list = profiles_rp.selected if profiles_rp else []
        simulations_rp = ctx.resources.get("simulations")
        sim_list = simulations_rp.selected if simulations_rp else []
        scenarios_rp = ctx.resources.get("scenarios")
        scenario_list = scenarios_rp.selected if scenarios_rp else []

        # --- Phase 4: Build profile name map ---
        profile_name_by_id: dict[str, str | None] = {
            str(item.id): item.name for item in profile_list if item.id is not None
        }

        # --- Phase 5: Build rows ---
        all_rows = build_leaderboard_rows_v3(
            attempt_chats=attempt_chats,
            attempt_messages=attempt_messages,
            profile_name_by_id=profile_name_by_id,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            rank_offset=request.page_offset,
        )

        # Paginate
        page_start = request.page_offset
        page_end = request.page_offset + request.page_limit
        total_count = len(all_rows)
        data_page = all_rows[page_start:page_end]

        # --- Phase 6: Build resources ---
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

        # --- Phase 7: Build filter options ---
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

        api_response = ListLeaderboardResponse(
            data=data_page,
            resources=resources,
            total_count=total_count,
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
            operation="leaderboard_search",
            request=http_request,
        )
