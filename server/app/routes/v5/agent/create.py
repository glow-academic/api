"""Agent create endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.create import create_agent_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.agent.types import (
    CreateAgentApiRequest,
    CreateAgentApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/create", response_model=CreateAgentApiResponse)
async def create_agent(
    request: CreateAgentApiRequest,
    http_request: Request,
    response: Response,
) -> CreateAgentApiResponse:
    """Create agents using composable infra architecture."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateAgentApiResponse:
            return await create_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.agents,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="create",
            arguments={
                "agents": [item.model_dump(mode="json") for item in request.agents]
            },
            response_model=CreateAgentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "agents"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
