"""Attempt start — unified endpoint for creating attempts.

POST /attempt/start — accepts home_id or practice_id. Routed through the audit
wrapper (idempotency replay + soft/accept staging of the dormant attempt).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.start import (
    AttemptStartRequest,
    AttemptStartResponse,
    attempt_start_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/start", response_model=AttemptStartResponse)
async def start_attempt(
    request: AttemptStartRequest,
    http_request: Request,
) -> AttemptStartResponse:
    """Create a new attempt from a home or practice entry."""
    profile_id_str = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)

    if not profile_id_str:
        raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID is required. Please sign in again.")
    profile_id = UUID(profile_id_str)
    pool = get_pool()
    redis = get_redis_client()

    try:
        # Resolve time-windowed group for audit linking.
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
        )
        group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None

        async def _runner(call_id: UUID | None = None) -> AttemptStartResponse:
            return await attempt_start_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
                soft=request.soft,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
                call_id=call_id,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="start",
            arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
            operation_key=request.idempotency_key,  # idempotency replay gate
            response_model=AttemptStartResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="attempt_start",
            request=http_request,
        )
