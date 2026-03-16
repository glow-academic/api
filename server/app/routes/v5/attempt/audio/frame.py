"""Attempt audio frame — thin HTTP adapter over internal orchestration.

Mirrors socket event: attempt_audio_frame.

Supports two modes:
  - upload_id: resolve an already-uploaded file and read its bytes
  - audio: base64-encoded raw PCM16 bytes (direct, like the socket)

Exactly one of upload_id or audio must be provided.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, model_validator

from app.infra.globals import get_pool, get_upload_folder
from app.infra.websocket.attempt.audio_frame import (
    attempt_audio_frame_internal_impl,
)
from app.tools.entries.uploads.get import get_upload

router = APIRouter()


class AudioFramePayload(BaseModel):
    chat_id: UUID
    upload_id: UUID | None = None
    audio: str | None = None  # base64-encoded PCM16 bytes

    @model_validator(mode="after")
    def exactly_one_source(self) -> "AudioFramePayload":
        if self.upload_id is None and self.audio is None:
            raise ValueError("Provide either upload_id or audio (base64)")
        if self.upload_id is not None and self.audio is not None:
            raise ValueError("Provide only one of upload_id or audio, not both")
        return self


class AudioFrameResponse(BaseModel):
    accepted: bool


@router.post("/frame", response_model=AudioFrameResponse)
async def audio_frame(
    request: AudioFramePayload,
    http_request: Request,
) -> AudioFrameResponse:
    """Push audio bytes into the session inbound queue."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    # Resolve audio bytes from either source
    if request.audio is not None:
        # Direct base64-encoded bytes (like socket)
        try:
            audio_bytes = base64.b64decode(request.audio)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 audio data")
    else:
        # Read from uploaded file
        assert request.upload_id is not None
        pool = get_pool()
        async with pool.acquire() as conn:
            upload = await get_upload(conn, request.upload_id)

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

    return AudioFrameResponse(accepted=accepted)
