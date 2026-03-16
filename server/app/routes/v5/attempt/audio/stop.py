"""Attempt audio stop — thin HTTP adapter over internal orchestration.

Mirrors socket event: attempt_audio_stop.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.attempt.audio_stop import (
    AudioStopInternalResult,
    attempt_audio_stop_internal_impl,
)

router = APIRouter()


class AudioStopPayload(BaseModel):
    chat_id: UUID


@router.post("/stop", response_model=AudioStopInternalResult)
async def audio_stop(
    request: AudioStopPayload,
    http_request: Request,
) -> AudioStopInternalResult:
    """Stop an audio session for an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    try:
        return await attempt_audio_stop_internal_impl(
            {"chat_id": str(request.chat_id)}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
