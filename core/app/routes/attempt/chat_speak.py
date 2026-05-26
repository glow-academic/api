"""Chat speak — push audio frames into a conversation buffer.

POST /attempt/chat/speak

Pure data primitive. Pushes PCM bytes into the session's inbound queue.
No DB, no AI. Keyed on conversation_id (or chat_id to resolve it).

Soft/accept (record-and-hold, in-memory): mirrors refresh's lightweight
"record intent, don't run it yet" lifecycle — but since the inbound queue is
in-memory, the staging buffer lives on the session (``pending_frames``), not in
Postgres. ``soft=True`` holds the frame (keyed by idempotency_key) WITHOUT
pushing it; the ack ({idempotency_key, accept}) flushes the staged frames into
the live queue (accept) or drops them (reject). ``soft=False`` pushes
immediately (the real-time hot path — no wrapper, no per-frame DB write). Lets
a benchmark stage a sequence of audio frames and replay them on accept.
"""

from __future__ import annotations

import asyncio
import base64
import time
from uuid import UUID, uuid4

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
    audio: str | None = None  # base64-encoded PCM16 bytes
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatSpeakResponse(BaseModel):
    accepted: bool
    idempotency_key: str | None = None


def _resolve_session(request: ChatSpeakRequest):
    if request.conversation_id:
        return get_session_by_conversation_id(str(request.conversation_id))
    if request.chat_id:
        return get_session_by_chat_id(str(request.chat_id))
    return None


def _enqueue(session, frame: bytes) -> bool:
    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": frame})
        return True
    except asyncio.QueueFull:
        return False


@router.post("/chat_speak", response_model=ChatSpeakResponse)
async def chat_speak(
    request: ChatSpeakRequest,
    http_request: Request,
) -> ChatSpeakResponse:
    """Push audio bytes into a conversation's inbound buffer (or stage them)."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    session = _resolve_session(request)
    if not session:
        raise HTTPException(status_code=404, detail="No active audio session")

    # ── Ack: flush (accept) or drop (reject) the staged frames ──
    if request.accept is not None and request.idempotency_key is not None:
        key = str(request.idempotency_key)
        staged = session.pending_frames.pop(key, [])
        if request.accept:
            ok = all(_enqueue(session, f) for f in staged) if staged else True
            return ChatSpeakResponse(accepted=ok, idempotency_key=key)
        return ChatSpeakResponse(accepted=False, idempotency_key=key)

    # Decode the inbound frame (required for stage + live push).
    if not request.audio:
        raise HTTPException(status_code=400, detail="audio is required")
    try:
        audio_bytes = base64.b64decode(request.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")
    if not audio_bytes:
        return ChatSpeakResponse(accepted=False)

    # ── Soft propose: hold the frame, don't push it ──
    if request.soft:
        key = str(request.idempotency_key or uuid4())
        session.pending_frames.setdefault(key, []).append(audio_bytes)
        return ChatSpeakResponse(accepted=True, idempotency_key=key)

    # ── Live: push immediately (real-time hot path) ──
    return ChatSpeakResponse(accepted=_enqueue(session, audio_bytes))
