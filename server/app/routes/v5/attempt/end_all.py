"""Attempt end-all endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptEndAllPayload
from app.infra.attempt.end_all import (
    attempt_end_all_internal_impl,
)

router = APIRouter()


class EndAllAttemptApiResponse(BaseModel):
    attempt_id: str
    success: bool
    all_scenarios_complete: bool = False
    message: str | None = None


@router.post("/end-all", response_model=EndAllAttemptApiResponse)
async def end_all_attempt(
    request: AttemptEndAllPayload,
    http_request: Request,
) -> EndAllAttemptApiResponse:
    """End all remaining chats in an attempt."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_end_all_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EndAllAttemptApiResponse.model_validate(result.model_dump(mode="json"))
