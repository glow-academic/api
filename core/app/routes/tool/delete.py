"""Tool delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.tool.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.delete import delete_tool_impl
from app.infra.tool.group import group_tool_impl
from app.infra.tool.types import (
    DeleteToolApiRequest,
    DeleteToolApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteToolApiResponse)
async def delete_tool(
    request: DeleteToolApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteToolApiResponse:
    """Bulk delete tools — composable infra architecture."""
    tags = ["tools"]

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
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> DeleteToolApiResponse:
            return await delete_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.tool_ids,
                session_id=session_id,
                accept=request.accept if request.idempotency_key else None,
                idempotency_key=request.idempotency_key,
                # All-matching path
                all=bool(request.all),
                excluded_ids=request.excluded_ids,
                search=request.search,
                filter_department_ids=request.filter_department_ids,
                filter_creatable=request.filter_creatable,
                filter_agent_ids=request.filter_agent_ids,
                department_search=request.department_search,
                flag_search=request.flag_search,
                agent_search=request.agent_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json", exclude_none=True),
            response_model=DeleteToolApiResponse,
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
            operation="delete_tool",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
