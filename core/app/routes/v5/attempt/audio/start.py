"""Attempt audio start — thin HTTP adapter over internal orchestration.

Mirrors socket event: attempt_audio_start.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.attempt.audio_start import (
    AudioStartInternalResult,
    attempt_audio_start_internal_impl,
)

router = APIRouter()


class AudioStartPayload(BaseModel):
    chat_id: UUID


@router.post("/start", response_model=AudioStartInternalResult)
async def audio_start(
    request: AudioStartPayload,
    http_request: Request,
) -> AudioStartInternalResult:
    """Start an audio session for an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await attempt_audio_start_internal_impl(
            {
                "chat_id": str(request.chat_id),
                "profile_id": str(profile_id),
                "session_id": str(session_id),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
