"""Tool preview endpoint — render Jinja output templates against mock args.

Thin route handler. Core logic lives in app.infra.tool.preview.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.group import group_tool_impl
from app.infra.tool.preview import preview_tool_impl
from app.infra.tool.types import (
    PreviewToolApiRequest,
    PreviewToolApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/preview", response_model=PreviewToolApiResponse)
async def preview_tool(
    request: PreviewToolApiRequest,
    http_request: Request,
    response: Response,
) -> PreviewToolApiResponse:
    """Render output templates against mock arg values."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        pool = get_pool()
        redis = get_redis_client()

        group_id = None
        if session_id:
            group_result = await group_tool_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> PreviewToolApiResponse:
            return await preview_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                request=request,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            operation="preview",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            runner=_runner,
            upload_folder=get_upload_folder(),
            response_model=PreviewToolApiResponse,
        )

        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="preview_tool",
            request=http_request,
        )
