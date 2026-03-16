"""Attempt start endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptStartPayload
from app.infra.attempt.start import attempt_start_internal_impl

router = APIRouter()


class StartAttemptApiResponse(BaseModel):
    attempt_id: str
    chat_entry_id: str | None = None
    attempt_chat_id: str | None = None


@router.post("/start", response_model=StartAttemptApiResponse)
async def start_attempt(
    request: AttemptStartPayload,
    http_request: Request,
) -> StartAttemptApiResponse:
    """Create a new attempt using the canonical internal attempt orchestration."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)

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

    try:
        result = await attempt_start_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StartAttemptApiResponse.model_validate(result.model_dump(mode="json"))
