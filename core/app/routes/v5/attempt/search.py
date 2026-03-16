"""Attempt search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.attempt.search import search_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.attempt.types import SearchAttemptApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchAttemptApiRequest(BaseModel):
    """Request model for attempt search endpoint."""

    # Main filters
    search: str | None = None
    simulation_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    practice: bool | None = None
    is_archived: bool | None = None
    infinite_mode: bool | None = None
    start_date: str | None = None
    end_date: str | None = None
    # Facet search text
    simulation_search: str | None = None
    department_search: str | None = None
    # Pagination
    page_size: int = 20
    page_offset: int = 0


@router.post("/search", response_model=SearchAttemptApiResponse)
async def search_attempt(
    request: SearchAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> SearchAttemptApiResponse:
    """Search attempts — composable infra architecture."""
    tags = ["attempts"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> SearchAttemptApiResponse:
            return await search_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                simulation_ids=request.simulation_ids,
                department_ids=request.department_ids,
                practice=request.practice,
                is_archived=request.is_archived,
                infinite_mode=request.infinite_mode,
                start_date=request.start_date,
                end_date=request.end_date,
                simulation_search=request.simulation_search,
                department_search=request.department_search,
                page_size=request.page_size,
                page_offset=request.page_offset,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            artifact="attempt",
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=SearchAttemptApiResponse,
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
            operation="search_attempt",
            request=http_request,
        )
