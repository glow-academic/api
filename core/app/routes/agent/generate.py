"""Agent generate endpoint — HTTP adapter for per-artifact generation.

Thin route handler. Core logic lives in app.infra.agent.generate.
Fire-and-return: progress/completion events arrive via SSE at /stream.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.agent.generate import generate_agent_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.websocket.generation_types import (
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/generate", response_model=ArtifactGenerateResponse)
async def generate_agent(
    request: ArtifactGenerateRequest,
    http_request: Request,
) -> ArtifactGenerateResponse:
    """Trigger agent generation. Returns immediately; progress via events."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ArtifactGenerateResponse:
            return await generate_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=session_id,
            operation="generate",
            arguments=request.model_dump(mode="json"),
            response_model=ArtifactGenerateResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="generate_agent",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
