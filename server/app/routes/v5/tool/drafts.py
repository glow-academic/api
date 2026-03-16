"""Tool drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.tool.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.drafts import list_tool_drafts_impl
from app.infra.tool.types import GetToolDraftsApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetToolDraftsApiResponse)
async def get_tool_drafts(
    http_request: Request,
    response: Response,
) -> GetToolDraftsApiResponse:
    """List tool drafts owned by the current profile."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        async def _runner() -> GetToolDraftsApiResponse:
            context = await list_tool_drafts_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                bypass_cache=bypass_cache,
            )
            return GetToolDraftsApiResponse(entries=context.entries.get("drafts"))

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=UUID(profile_id),
            session_id=http_request.state.session_id,
            operation="drafts",
            arguments={},
            bypass_cache=bypass_cache,
            response_model=GetToolDraftsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "tools,drafts"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_tool_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
