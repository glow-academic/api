"""Attempt complete — mark an entire attempt as completed.

POST /attempt/complete
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.complete import complete_attempt_impl
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class AttemptCompleteRequest(BaseModel):
    attempt_id: UUID
    message: str = ""


class AttemptCompleteResponse(BaseModel):
    success: bool
    completion_id: str
    attempt_id: str


@router.post("/complete", response_model=AttemptCompleteResponse)
async def attempt_complete(
    request: AttemptCompleteRequest,
    http_request: Request,
) -> AttemptCompleteResponse:
    """Mark an entire attempt as completed."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    redis = get_redis_client()

    try:
        result = await complete_attempt_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            attempt_id=request.attempt_id,
            message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AttemptCompleteResponse(
        success=True,
        completion_id=result["completion_id"],
        attempt_id=result["attempt_id"],
    )
