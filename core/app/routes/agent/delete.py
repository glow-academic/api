"""Agent delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.delete import delete_agent_impl
from app.infra.agent.group import group_agent_impl
from app.infra.agent.types import (
    DeleteAgentApiRequest,
    DeleteAgentApiResponse,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteAgentApiResponse)
async def delete_agent(
    request: DeleteAgentApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteAgentApiResponse:
    """Bulk delete agents — composable infra architecture."""
    tags = ["agents"]

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
            group_result = await group_agent_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None
        premint_call_id = None if is_ack else request.idempotency_key

        async def _runner() -> DeleteAgentApiResponse:
            return await delete_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.agent_ids,
                session_id=session_id,
                soft=request.soft,
                accept=request.accept if request.idempotency_key else None,
                idempotency_key=request.idempotency_key,
                # All-matching path
                all=bool(request.all),
                excluded_ids=request.excluded_ids,
                search=request.search,
                filter_department_ids=request.filter_department_ids,
                filter_model_ids=request.filter_model_ids,
                filter_tool_ids=request.filter_tool_ids,
                department_search=request.department_search,
                model_search=request.model_search,
                tool_search=request.tool_search,
                flag_search=request.flag_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteAgentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
            call_id=premint_call_id,  # pre-mint calls_entry with client key (HTTP soft FK)
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
