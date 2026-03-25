"""Agent delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.delete import delete_agent_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.agent.types import (
    DeleteAgentApiRequest,
    DeleteAgentApiResponse,
)
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

        async def _runner() -> DeleteAgentApiResponse:
            return await delete_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                agent_ids=request.agent_ids,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=session_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteAgentApiResponse,
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
            operation="delete_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
