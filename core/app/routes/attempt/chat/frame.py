"""Chat frame — send an audio segment via audio_id reference.

Was: POST /attempt/audio/frame (accepted upload_id or raw base64)
Now: POST /attempt/chat/frame (audio_id only, from /attempt/audio/upload)
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool, get_upload_folder
from app.infra.websocket.attempt.audio_frame import (
    attempt_audio_frame_internal_impl,
)
from app.tools.entries.uploads.get import get_upload

router = APIRouter()


class ChatFrameRequest(BaseModel):
    chat_id: UUID
    audio_id: UUID  # from /attempt/audio/upload


class ChatFrameResponse(BaseModel):
    accepted: bool


@router.post("/frame", response_model=ChatFrameResponse)
async def chat_frame(
    request: ChatFrameRequest,
    http_request: Request,
) -> ChatFrameResponse:
    """Send an audio segment into the voice session via audio_id reference."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    # Read audio bytes from the uploaded file
    pool = get_pool()
    async with pool.acquire() as conn:
        upload = await get_upload(conn, request.audio_id)

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_path = get_upload_folder() / upload.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Upload file not found on disk")

    audio_bytes = Path(file_path).read_bytes()

    accepted = attempt_audio_frame_internal_impl(
        chat_id=str(request.chat_id),
        audio=audio_bytes,
    )

    return ChatFrameResponse(accepted=accepted)
