"""Chat send — unified input endpoint for text and audio.

POST /attempt/chat/send

Accepts text input, audio input (via audio_id from upload), or both.
Routes through the appropriate pipeline based on whether a voice session
is active on the chat.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, model_validator

from app.infra.attempt.message import attempt_message_internal_impl
from app.infra.globals import get_pool, get_upload_folder
from app.infra.websocket.attempt.audio_frame import (
    attempt_audio_frame_internal_impl,
)
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.uploads.get import get_upload

router = APIRouter()


class ChatSendRequest(BaseModel):
    chat_id: UUID
    text: str | None = None
    audio_id: UUID | None = None
    parent_message_id: UUID | None = None

    @model_validator(mode="after")
    def at_least_one_input(self) -> "ChatSendRequest":
        if self.text is None and self.audio_id is None:
            raise ValueError("Provide at least one of text or audio_id")
        return self


class ChatSendResponse(BaseModel):
    accepted: bool
    message_id: UUID


@router.post("/send", response_model=ChatSendResponse)
async def chat_send(
    request: ChatSendRequest,
    http_request: Request,
) -> ChatSendResponse:
    """Send text or audio input to an attempt chat.

    Routing logic:
    - Voice session active + audio_id → feed audio to voice pipeline
    - Voice session active + text → feed text to voice pipeline (TTS)
    - No voice session + text → standard text generation pipeline
    - No voice session + audio_id → STT → standard text pipeline
    """
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    message_id = uuid4()
    voice_session = get_session_by_chat_id(str(request.chat_id))

    # --- Audio path: resolve bytes from upload ---
    audio_bytes: bytes | None = None
    if request.audio_id is not None:
        pool = get_pool()
        async with pool.acquire() as conn:
            upload = await get_upload(conn, request.audio_id)
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")
        file_path = get_upload_folder() / upload.file_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Upload file not found on disk")
        audio_bytes = Path(file_path).read_bytes()

    # --- Voice session active: route through voice pipeline ---
    if voice_session is not None:
        if audio_bytes is not None:
            accepted = attempt_audio_frame_internal_impl(
                chat_id=str(request.chat_id),
                audio=audio_bytes,
            )
            return ChatSendResponse(accepted=accepted, message_id=message_id)

        # Text into voice session — push as text message
        if request.text is not None:
            await voice_session.inbound_queue.put(
                {"type": "text", "content": request.text}
            )
            return ChatSendResponse(accepted=True, message_id=message_id)

    # --- No voice session: standard text pipeline ---
    text = request.text or ""

    try:
        result = await attempt_message_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                "chat_id": str(request.chat_id),
                "message": text,
                **(
                    {"parent_message_id": str(request.parent_message_id)}
                    if request.parent_message_id
                    else {}
                ),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result_message_id = result.user_message_id or str(message_id)
    return ChatSendResponse(accepted=True, message_id=UUID(result_message_id))
