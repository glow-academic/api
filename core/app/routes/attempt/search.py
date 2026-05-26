"""Canonical attempt search endpoint.

This is the single endpoint clients call for paginated attempt history. The
previous per-view ``/attempt/{home,practice,dashboard}/search`` routes were
collapsed into this one; view intent is now expressed entirely through filter
parameters (``practice``, ``target_profile_id``, ``profile_ids``, etc.).

Response is ``HistoryResponse`` with full display aggregates (score%, persona,
time, etc.) shaped for all consumers. Routed through the audit wrapper so
``snapshot_key`` replays a consistent view across related reads.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.api_types import HistoryResponse
from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.search import search_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchAttemptApiRequest(BaseModel):
    """Request model for canonical attempt search.

    Filters cover all view contexts (home, practice, dashboard, record):
    - ``practice=False`` → home-style filtering (general attempts only)
    - ``practice=True`` → practice-style filtering
    - ``practice=None`` → no constraint (dashboard default)
    - ``target_profile_id`` → record-style scoping to a single profile
    """

    # Visibility / scoping
    target_profile_id: UUID | None = Field(None, description="Scope to a single profile (record-style)")
    profile_ids: list[UUID] | None = Field(None, description="Filter to specific profiles (intersected with visible set)")

    # Filters
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    role_ids: list[UUID] | None = Field(None, description="Role resource IDs to filter profiles by")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation IDs to filter by")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    practice: bool | None = Field(None, description="True=practice-only, False=general-only, None=both")
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    show_archived: bool = Field(False, description="Include archived attempts")
    start_date: str | None = Field(None, description="Filter start date (ISO)")
    end_date: str | None = Field(None, description="Filter end date (ISO)")

    # Text search
    simulation_search: str | None = Field(None, description="Substring match on simulation_name")
    scenario_search: str | None = Field(None, description="Substring match on scenario titles")
    profile_search: str | None = Field(None, description="Substring match on profile_name")

    # Sort / pagination
    sort_by: str = Field("date", description="Sort field")
    sort_order: str = Field("desc", description="Sort direction (asc or desc)")
    page: int = Field(0, description="Page number")
    page_size: int = Field(20, description="Items per page")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


@router.post("/search", response_model=HistoryResponse)
async def search_attempt(
    request: SearchAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> HistoryResponse:
    """Search paginated attempt history. Canonical for all view contexts."""
    tags = ["artifacts", "attempts", "history"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    profile_id = http_request.state.profile_id
    if not profile_id:
        raise HTTPException(
            status_code=401,
            detail="Profile ID is required. Please sign in again.",
        )
    session_id = getattr(http_request.state, "session_id", None)

    cache_key_val = cache_key(
        http_request.url.path,
        {
            "profile_id": str(profile_id),
            "request": request.model_dump(mode="json"),
        },
    )

    try:
        pool = get_pool()
        redis = get_redis_client()

        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> HistoryResponse:
            if not bypass_cache:
                cached = await get_cached(cache_key_val, redis=redis)
                if cached:
                    response.headers["X-Cache-Hit"] = "1"
                    return HistoryResponse.model_validate(cached["data"])

            api_response = await search_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                target_profile_id=request.target_profile_id,
                profile_ids=request.profile_ids,
                cohort_ids=request.cohort_ids,
                department_ids=request.department_ids,
                role_ids=request.role_ids,
                simulation_ids=request.simulation_ids,
                scenario_ids=request.scenario_ids,
                practice=request.practice,
                infinite_mode=request.infinite_mode,
                show_archived=request.show_archived,
                start_date=request.start_date,
                end_date=request.end_date,
                simulation_search=request.simulation_search,
                scenario_search=request.scenario_search,
                profile_search=request.profile_search,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
                page=request.page,
                page_size=request.page_size,
                bypass_cache=bypass_cache,
            )
            await set_cached(
                cache_key_val,
                {"data": api_response.model_dump(mode="json")},
                ttl=300,
                tags=tags,
                redis=redis,
            )
            response.headers.setdefault("X-Cache-Hit", "0")
            return api_response

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=HistoryResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
        )
        response.headers["X-Cache-Tags"] = ",".join(tags)
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="attempt_search",
            request=http_request,
        )
