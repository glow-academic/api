"""Tool update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.tool.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.group import group_tool_impl
from app.infra.tool.update import update_tool_impl
from app.infra.tool.types import (
    UpdateToolApiRequest,
    UpdateToolApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateToolApiResponse)
async def update_tool(
    request: UpdateToolApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateToolApiResponse:
    """Update tools using composable infra architecture."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_tool_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> UpdateToolApiResponse:
            return await update_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                request=request,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="update",
            arguments={
                "tools": [item.model_dump(mode="json") for item in request.tools]
            },
            response_model=UpdateToolApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "tools"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_tool",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
