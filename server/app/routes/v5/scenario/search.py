"""Scenario search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.scenario.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.scenario.search import search_scenario_impl
from app.infra.scenario.types import ListScenarioApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchScenarioApiRequest(BaseModel):
    """Request model for scenario search endpoint."""

    # Main filters
    search: str | None = None
    persona_ids: list[UUID] | None = None
    simulation_ids: list[UUID] | None = None
    filter_department_ids: list[UUID] | None = None
    # Facet search text
    persona_search: str | None = None
    simulation_search: str | None = None
    department_search: str | None = None
    flag_search: str | None = None
    # Pagination
    page_size: int | None = 10
    page_offset: int | None = 0


@router.post("/search", response_model=ListScenarioApiResponse)
async def search_scenario(
    request: SearchScenarioApiRequest,
    http_request: Request,
    response: Response,
) -> ListScenarioApiResponse:
    """Search scenarios — composable infra architecture."""
    tags = ["scenarios"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListScenarioApiResponse:
            return await search_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                persona_ids=request.persona_ids,
                simulation_ids=request.simulation_ids,
                filter_department_ids=request.filter_department_ids,
                persona_search=request.persona_search,
                simulation_search=request.simulation_search,
                department_search=request.department_search,
                flag_search=request.flag_search,
                page_size=request.page_size or 10,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListScenarioApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="search_scenario",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
