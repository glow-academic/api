"""Attempt speak — push audio bytes into a conversation buffer.

POST /attempt/speak — accepts conversation_id + base64-encoded audio.
No DB, no AI. Just pushes bytes into the session's inbound queue.
"""

from __future__ import annotations

import asyncio
import base64
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.session_store import get_session_by_conversation_id

router = APIRouter()


class AttemptSpeakRequest(BaseModel):
    conversation_id: UUID
    audio: str  # base64-encoded PCM16 bytes


class AttemptSpeakResponse(BaseModel):
    accepted: bool


@router.post("/speak", response_model=AttemptSpeakResponse)
async def attempt_speak(
    request: AttemptSpeakRequest,
    http_request: Request,
) -> AttemptSpeakResponse:
    """Push audio bytes into a conversation's inbound buffer."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    session = get_session_by_conversation_id(str(request.conversation_id))
    if not session:
        raise HTTPException(status_code=404, detail="No active session for this conversation")

    try:
        audio_bytes = base64.b64decode(request.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    if not audio_bytes:
        return AttemptSpeakResponse(accepted=False)

    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": audio_bytes})
        return AttemptSpeakResponse(accepted=True)
    except asyncio.QueueFull:
        return AttemptSpeakResponse(accepted=False)
