"""Chat silence — end a voice session.

Was: POST /attempt/audio/stop
Now: POST /attempt/chat/silence
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.attempt.chat.silence import (
    AudioStopInternalResult,
    attempt_chat_silence_internal_impl,
)

router = APIRouter()


class ChatSilenceRequest(BaseModel):
    chat_id: UUID
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


@router.post("/chat_silence", response_model=AudioStopInternalResult)
async def chat_silence(
    request: ChatSilenceRequest,
    http_request: Request,
) -> AudioStopInternalResult:
    """End a voice session for an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    try:
        return await attempt_chat_silence_internal_impl(
            {
                "chat_id": str(request.chat_id),
                "profile_id": str(profile_id) if profile_id else None,
                "session_id": str(session_id) if session_id else None,
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
