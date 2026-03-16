"""Test search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.test.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.test.search import search_test_impl
from app.infra.test.types import SearchTestApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchTestApiRequest(BaseModel):
    """Request model for test search endpoint."""

    # Main filters
    eval_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    is_archived: bool | None = None
    start_date: str | None = None
    end_date: str | None = None
    # Facet search text
    eval_search: str | None = None
    department_search: str | None = None
    # Pagination
    page_size: int = 20
    page_offset: int = 0


@router.post("/search", response_model=SearchTestApiResponse)
async def search_test(
    request: SearchTestApiRequest,
    http_request: Request,
    response: Response,
) -> SearchTestApiResponse:
    """Search tests — composable infra architecture."""
    tags = ["tests"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> SearchTestApiResponse:
            return await search_test_impl(
                pool,
                redis,
                profile_id=profile_id,
                eval_ids=request.eval_ids,
                department_ids=request.department_ids,
                is_archived=request.is_archived,
                start_date=request.start_date,
                end_date=request.end_date,
                eval_search=request.eval_search,
                department_search=request.department_search,
                page_size=request.page_size,
                page_offset=request.page_offset,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            artifact="test",
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=SearchTestApiResponse,
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
            operation="search_test",
            request=http_request,
        )
