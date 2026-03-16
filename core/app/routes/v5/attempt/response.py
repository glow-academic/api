"""Attempt response endpoint — submit a video question response.

Synchronous equivalent of socket event: attempt_response_submit.
Reuses: socket/client/attempt/response.py infra.

TODO: Wire to actual infra (record response, return correctness).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptResponsePayload
from app.infra.attempt.response import (
    attempt_response_internal_impl,
)

router = APIRouter()


class ResponseAttemptApiResponse(BaseModel):
    success: bool
    message: str | None = None
    is_correct: bool | None = None
    response_id: str | None = None


@router.post("/response", response_model=ResponseAttemptApiResponse)
async def attempt_response(
    request: AttemptResponsePayload,
    http_request: Request,
) -> ResponseAttemptApiResponse:
    """Submit a video question response."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_response_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ResponseAttemptApiResponse.model_validate(result.model_dump(mode="json"))
