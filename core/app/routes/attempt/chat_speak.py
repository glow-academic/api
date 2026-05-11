"""Chat speak — push audio frames into a conversation buffer.

POST /attempt/chat/speak

Pure data primitive. Pushes PCM bytes into the session's inbound queue.
No DB, no AI. Keyed on conversation_id (or chat_id to resolve it).
"""

from __future__ import annotations

import asyncio
import base64
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.session_store import (
    get_session_by_chat_id,
    get_session_by_conversation_id,
)

router = APIRouter()


class ChatSpeakRequest(BaseModel):
    conversation_id: UUID | None = None
    chat_id: UUID | None = None
    audio: str  # base64-encoded PCM16 bytes


class ChatSpeakResponse(BaseModel):
    accepted: bool


@router.post("/chat_speak", response_model=ChatSpeakResponse)
async def chat_speak(
    request: ChatSpeakRequest,
    http_request: Request,
) -> ChatSpeakResponse:
    """Push audio bytes into a conversation's inbound buffer."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    # Resolve session from conversation_id or chat_id
    session = None
    if request.conversation_id:
        session = get_session_by_conversation_id(str(request.conversation_id))
    elif request.chat_id:
        session = get_session_by_chat_id(str(request.chat_id))

    if not session:
        raise HTTPException(status_code=404, detail="No active audio session")

    try:
        audio_bytes = base64.b64decode(request.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    if not audio_bytes:
        return ChatSpeakResponse(accepted=False)

    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": audio_bytes})
        return ChatSpeakResponse(accepted=True)
    except asyncio.QueueFull:
        return ChatSpeakResponse(accepted=False)
