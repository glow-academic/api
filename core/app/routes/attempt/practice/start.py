"""Practice start endpoint — thin HTTP adapter.

POST /attempt/practice/start — creates an attempt from a practice entry.
Returns { attempt_id, chat_id }. Does NOT create attempt_chat or trigger generation.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.practice_start import (
    AttemptStartResponse,
    PracticeStartRequest,
    practice_start_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/start", response_model=AttemptStartResponse)
async def start_practice_attempt(
    request: PracticeStartRequest,
    http_request: Request,
) -> AttemptStartResponse:
    """Create a new attempt from a practice entry."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID is required. Please sign in again.")

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> AttemptStartResponse:
            return await practice_start_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        return await run_artifact_operation_with_audit(
            pool, redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            operation="start",
            arguments=request.model_dump(mode="json"),
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
            operation="start_practice_attempt",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
