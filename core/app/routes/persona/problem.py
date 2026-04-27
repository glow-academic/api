"""Persona problem endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.persona.problem.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.persona.group import group_persona_impl
from app.infra.persona.problem import problem_persona_impl
from app.infra.persona.types import (
    ProblemPersonaApiRequest,
    ProblemPersonaApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/problem", response_model=ProblemPersonaApiResponse)
async def problem_persona(
    request: ProblemPersonaApiRequest,
    http_request: Request,
    response: Response,
) -> ProblemPersonaApiResponse:
    """Report a persona problem — composable infra architecture."""
    tags = ["personas", "problems"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        group_result = await group_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

        async def _runner() -> ProblemPersonaApiResponse:
            return await problem_persona_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                type=request.type,
                message=request.message,
                idempotency_key=request.idempotency_key,
                accept=request.accept if request.idempotency_key else None,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="persona",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="problem",
            arguments=request.model_dump(mode="json"),
            response_model=ProblemPersonaApiResponse,
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
            operation="problem_persona",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
