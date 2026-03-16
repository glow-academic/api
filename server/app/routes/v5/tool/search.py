"""Tool search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.tool.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.search import search_tool_impl
from app.infra.tool.types import ListToolApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchToolApiRequest(BaseModel):
    """Request model for tool search endpoint."""

    # Main filters
    search: str | None = None
    filter_department_ids: list[UUID] | None = None
    filter_agent_ids: list[UUID] | None = None
    filter_creatable: list[str] | None = None
    # Facet search text
    department_search: str | None = None
    agent_search: str | None = None
    # Pagination
    page_size: int | None = 12
    page_offset: int | None = 0


@router.post("/search", response_model=ListToolApiResponse)
async def search_tool(
    request: SearchToolApiRequest,
    http_request: Request,
    response: Response,
) -> ListToolApiResponse:
    """Search tools — composable infra architecture."""
    tags = ["tools"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListToolApiResponse:
            return await search_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                filter_department_ids=request.filter_department_ids,
                filter_agent_ids=request.filter_agent_ids,
                filter_creatable=request.filter_creatable,
                department_search=request.department_search,
                agent_search=request.agent_search,
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListToolApiResponse,
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
            operation="search_tool",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
