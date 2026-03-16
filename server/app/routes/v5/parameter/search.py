"""Parameter search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.parameter.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.parameter.search import search_parameter_impl
from app.infra.parameter.types import ListParameterApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchParameterApiRequest(BaseModel):
    """Request model for parameter search endpoint."""

    # Main filters
    search: str | None = None
    scenario_ids: list[UUID] | None = None
    field_ids: list[UUID] | None = None
    filter_department_ids: list[UUID] | None = None
    # Facet search text
    scenario_search: str | None = None
    field_search: str | None = None
    department_search: str | None = None
    # Pagination
    page_size: int | None = 12
    page_offset: int | None = 0


@router.post("/search", response_model=ListParameterApiResponse)
async def search_parameter(
    request: SearchParameterApiRequest,
    http_request: Request,
    response: Response,
) -> ListParameterApiResponse:
    """Search parameters — composable infra architecture."""
    tags = ["parameters"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListParameterApiResponse:
            return await search_parameter_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                scenario_ids=request.scenario_ids,
                field_ids=request.field_ids,
                filter_department_ids=request.filter_department_ids,
                scenario_search=request.scenario_search,
                field_search=request.field_search,
                department_search=request.department_search,
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="parameter",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListParameterApiResponse,
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
            operation="search_parameter",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
