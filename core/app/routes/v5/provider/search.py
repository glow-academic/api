"""Provider search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.provider.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.provider.search import search_provider_impl
from app.infra.provider.types import ListProviderApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchProviderApiRequest(BaseModel):
    """Request model for provider search endpoint."""

    # Main filters
    search: str | None = None
    filter_department_ids: list[UUID] | None = None
    filter_model_ids: list[UUID] | None = None
    filter_status: list[str] | None = None
    # Facet search text
    department_search: str | None = None
    model_search: str | None = None
    # Pagination
    page_size: int | None = 12
    page_offset: int | None = 0


@router.post("/search", response_model=ListProviderApiResponse)
async def search_provider(
    request: SearchProviderApiRequest,
    http_request: Request,
    response: Response,
) -> ListProviderApiResponse:
    """Search providers — composable infra architecture."""
    tags = ["providers"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListProviderApiResponse:
            return await search_provider_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                filter_department_ids=request.filter_department_ids,
                filter_model_ids=request.filter_model_ids,
                filter_status=request.filter_status,
                department_search=request.department_search,
                model_search=request.model_search,
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="provider",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListProviderApiResponse,
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
            operation="search_provider",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
