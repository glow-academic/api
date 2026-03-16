"""Attempt use-previous endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptUsePreviousPayload
from app.infra.attempt.use_previous import (
    attempt_use_previous_internal_impl,
)

router = APIRouter()


class UsePreviousAttemptApiResponse(BaseModel):
    success: bool
    message: str | None = None


@router.post("/use-previous", response_model=UsePreviousAttemptApiResponse)
async def attempt_use_previous(
    request: AttemptUsePreviousPayload,
    http_request: Request,
) -> UsePreviousAttemptApiResponse:
    """Copy grades from a previous attempt's chats."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_use_previous_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return UsePreviousAttemptApiResponse(
        success=result.success,
        message=result.message,
    )
