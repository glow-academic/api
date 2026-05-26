"""Simulation search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.simulation.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.search import search_simulation_impl
from app.infra.simulation.types import ListSimulationApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchSimulationApiRequest(BaseModel):
    """Request model for simulation search endpoint."""

    # Main filters
    search: str | None = None
    filter_scenario_ids: list[UUID] | None = None
    filter_cohort_ids: list[UUID] | None = None
    filter_department_ids: list[UUID] | None = None
    # Facet search text
    scenario_search: str | None = None
    cohort_search: str | None = None
    department_search: str | None = None
    flag_search: str | None = None
    # Pagination
    page_size: int | None = 10
    page_offset: int | None = 0
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


@router.post("/search", response_model=ListSimulationApiResponse)
async def search_simulation(
    request: SearchSimulationApiRequest,
    http_request: Request,
    response: Response,
) -> ListSimulationApiResponse:
    """Search simulations — composable infra architecture."""
    tags = ["simulations"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_simulation_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> ListSimulationApiResponse:
            return await search_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                filter_scenario_ids=request.filter_scenario_ids,
                filter_cohort_ids=request.filter_cohort_ids,
                filter_department_ids=request.filter_department_ids,
                scenario_search=request.scenario_search,
                cohort_search=request.cohort_search,
                department_search=request.department_search,
                flag_search=request.flag_search,
                page_size=request.page_size or 10,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListSimulationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="search_simulation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
