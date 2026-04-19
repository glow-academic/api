"""Attempt start — unified endpoint for creating attempts.

POST /attempt/start — accepts home_id or practice_id.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.start import (
    AttemptStartRequest,
    AttemptStartResponse,
    attempt_start_impl,
)
from app.infra.globals import get_pool, get_redis_client
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/start", response_model=AttemptStartResponse)
async def start_attempt(
    request: AttemptStartRequest,
    http_request: Request,
) -> AttemptStartResponse:
    """Create a new attempt from a home or practice entry."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)

    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID is required. Please sign in again.")

    try:
        return await attempt_start_impl(
            get_pool(),
            get_redis_client(),
            profile_id=profile_id,
            session_id=session_id,
            request=request,
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
