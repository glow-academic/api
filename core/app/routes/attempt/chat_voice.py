"""Chat voice — start a voice session on a chat.

Was: POST /attempt/audio/start
Now: POST /attempt/chat/voice
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.attempt.chat.voice import (
    AudioStartInternalResult,
    attempt_chat_voice_internal_impl,
)

router = APIRouter()


class ChatVoiceRequest(BaseModel):
    chat_id: UUID


@router.post("/chat_voice", response_model=AudioStartInternalResult)
async def chat_voice(
    request: ChatVoiceRequest,
    http_request: Request,
) -> AudioStartInternalResult:
    """Start a voice session for an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await attempt_chat_voice_internal_impl(
            {
                "chat_id": str(request.chat_id),
                "profile_id": str(profile_id),
                "session_id": str(session_id),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
