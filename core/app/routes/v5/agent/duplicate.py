"""Agent duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.duplicate import duplicate_agent_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.agent.types import (
    DuplicateAgentApiRequest,
    DuplicateAgentApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateAgentApiResponse,
)
async def duplicate_agent(
    request: DuplicateAgentApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateAgentApiResponse:
    """Duplicate an agent — composable infra architecture."""
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

        async def _runner() -> DuplicateAgentApiResponse:
            return await duplicate_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                agent_id=request.agent_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=session_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateAgentApiResponse,
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
            operation="duplicate_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
