"""Department search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.department.search.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.department.search import search_department_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.department.types import ListDepartmentApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchDepartmentApiRequest(BaseModel):
    """Request model for department search endpoint."""

    # Main filters
    search: str | None = None
    # Pagination
    page_size: int | None = 12
    page_offset: int | None = 0


@router.post("/search", response_model=ListDepartmentApiResponse)
async def search_department(
    request: SearchDepartmentApiRequest,
    http_request: Request,
    response: Response,
) -> ListDepartmentApiResponse:
    """Search departments — composable infra architecture."""
    tags = ["departments"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListDepartmentApiResponse:
            return await search_department_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="department",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListDepartmentApiResponse,
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
            operation="search_department",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
