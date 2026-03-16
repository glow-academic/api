"""Attempt stop endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptStopPayload
from app.infra.attempt.stop import attempt_stop_internal_impl

router = APIRouter()


class StopAttemptApiResponse(BaseModel):
    chat_id: str
    success: bool
    message: str | None = None


@router.post("/stop", response_model=StopAttemptApiResponse)
async def attempt_stop(
    request: AttemptStopPayload,
    http_request: Request,
) -> StopAttemptApiResponse:
    """Stop message generation for an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_stop_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StopAttemptApiResponse.model_validate(result.model_dump(mode="json"))
