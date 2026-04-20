"""Chat audio — attach audio to a chat message.

POST /attempt/chat/audio

Creates an ``attempt_audio_entry`` row linking a message to a
resource-level ``audios_id``. Thin route handler — core logic in
``app.infra.attempt.chat_audio``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.chat_audio import attempt_chat_audio_internal_impl
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class ChatAudioRequest(BaseModel):
    chat_id: UUID
    message_id: UUID
    audios_id: UUID


class ChatAudioResponse(BaseModel):
    success: bool
    attempt_audio_id: str


@router.post("/audio", response_model=ChatAudioResponse)
async def chat_audio(
    request: ChatAudioRequest,
    http_request: Request,
) -> ChatAudioResponse:
    """Attach an audios_id to an attempt chat message."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    redis = get_redis_client()

    try:
        result = await attempt_chat_audio_internal_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            message_id=request.message_id,
            audios_id=request.audios_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatAudioResponse(
        success=result.success, attempt_audio_id=result.attempt_audio_id,
    )
