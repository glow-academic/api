"""System generate endpoint — HTTP adapter for per-artifact generation.

Thin route handler. Core logic lives in app.infra.system.generate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.generate import generate_system_impl
from app.infra.websocket.generation_types import (
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
    GenerateConfig,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/generate", response_model=ArtifactGenerateResponse)
async def generate_system(
    request: ArtifactGenerateRequest,
    http_request: Request,
) -> ArtifactGenerateResponse:
    """Trigger system generation. Returns immediately; progress via events."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID is required. Please sign in again.")

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ArtifactGenerateResponse:
            return await generate_system_impl(
                pool, redis,
                profile_id=profile_id, session_id=session_id,
                **request.model_dump(exclude={"config"}, exclude_none=True),
                **(request.config or GenerateConfig()).model_dump(exclude_none=True),
            )

        return await run_artifact_operation_with_audit(
            pool, redis, artifact="system", profile_id=profile_id, session_id=session_id,
            operation="generate", arguments=request.model_dump(mode="json"),
            response_model=ArtifactGenerateResponse, runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(error=e, route_path=http_request.url.path, operation="generate_system",
                          sql_query=None, sql_params=None, request=http_request)
