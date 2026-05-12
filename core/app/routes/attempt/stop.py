"""POST /attempt/stop — thin HTTP adapter over stop_attempt_impl."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.stop import (
    AttemptStopRequest,
    AttemptStopResponse,
    stop_attempt_impl,
)

router = APIRouter()


@router.post("/stop", response_model=AttemptStopResponse)
async def attempt_stop(
    request: AttemptStopRequest,
    http_request: Request,
) -> AttemptStopResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")
    return await stop_attempt_impl(
        profile_id=profile_id,
        group_id=request.group_id,
    )
