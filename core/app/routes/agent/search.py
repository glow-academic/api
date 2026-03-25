"""Agent search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.agent.search import search_agent_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.agent.types import ListAgentApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchAgentApiRequest(BaseModel):
    """Request model for agent search endpoint."""

    # Main filters
    search: str | None = None
    filter_department_ids: list[UUID] | None = None
    filter_model_ids: list[UUID] | None = None
    filter_tool_ids: list[UUID] | None = None
    # Facet search text
    department_search: str | None = None
    model_search: str | None = None
    tool_search: str | None = None
    # Pagination
    page_size: int | None = 12
    page_offset: int | None = 0


@router.post("/search", response_model=ListAgentApiResponse)
async def search_agent(
    request: SearchAgentApiRequest,
    http_request: Request,
    response: Response,
) -> ListAgentApiResponse:
    """Search agents — composable infra architecture."""
    tags = ["agents"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListAgentApiResponse:
            return await search_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                search=request.search,
                filter_department_ids=request.filter_department_ids,
                filter_model_ids=request.filter_model_ids,
                filter_tool_ids=request.filter_tool_ids,
                department_search=request.department_search,
                model_search=request.model_search,
                tool_search=request.tool_search,
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListAgentApiResponse,
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
            operation="search_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
