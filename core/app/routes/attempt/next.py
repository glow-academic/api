"""Attempt next endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptNextPayload
from app.infra.attempt.next import attempt_next_internal_impl

router = APIRouter()


class NextAttemptApiResponse(BaseModel):
    attempt_id: str
    chat_id: str


@router.post("/next", response_model=NextAttemptApiResponse)
async def next_attempt(
    request: AttemptNextPayload,
    http_request: Request,
) -> NextAttemptApiResponse:
    """Proceed to the next scenario in an existing attempt."""
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
        result = await attempt_next_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return NextAttemptApiResponse(
        attempt_id=result.attempt_id,
        chat_id=result.attempt_chat_id or result.chat_entry_id or "",
    )
