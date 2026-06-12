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

AUTHZ: ownership is enforced inside the shared ``chat_speak_impl`` (W1) so the
HTTP route and its WS twin (``ws/attempt/speak.py``) can never diverge — only
the authenticated owner of the live session may push audio into it.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.speak import chat_speak_impl

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


@router.post("/chat_speak", response_model=ChatSpeakResponse)
async def chat_speak(
    request: ChatSpeakRequest,
    http_request: Request,
) -> ChatSpeakResponse:
    """Push audio bytes into a conversation's inbound buffer (or stage them)."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    result = chat_speak_impl(
        profile_id=profile_id,
        conversation_id=request.conversation_id,
        chat_id=request.chat_id,
        audio=request.audio,
        soft=request.soft,
        accept=request.accept,
        idempotency_key=request.idempotency_key,
    )

    if result.not_found:
        raise HTTPException(status_code=404, detail="No active audio session")
    # AUTHZ: non-owner caller — deny with NO side effect (W1).
    if result.denied:
        raise HTTPException(
            status_code=403, detail="You don't have access to this audio session."
        )
    if result.bad_audio:
        raise HTTPException(status_code=400, detail="audio is required")

    return ChatSpeakResponse(
        accepted=result.accepted, idempotency_key=result.idempotency_key
    )
