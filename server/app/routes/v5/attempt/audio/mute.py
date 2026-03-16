"""Attempt audio mute — thin HTTP adapter over internal orchestration.

Mirrors socket event: attempt_audio_mute.
"""

from __future__ import annotations

import uuid as uuid_mod
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.attempt_mutes.create import create_attempt_mutes
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class AudioMutePayload(BaseModel):
    chat_id: UUID
    muted: bool = False


class AudioMuteResponse(BaseModel):
    accepted: bool


@router.post("/mute", response_model=AudioMuteResponse)
async def audio_mute(
    request: AudioMutePayload,
    http_request: Request,
) -> AudioMuteResponse:
    """Toggle microphone mute for an audio session."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    session = get_session_by_chat_id(str(request.chat_id))
    if not session:
        raise HTTPException(
            status_code=404, detail="No active audio session for this chat"
        )

    # Record mute event in DB
    if session.conversation_id:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await create_attempt_mutes(
                    conn,
                    conversation_id=uuid_mod.UUID(session.conversation_id),
                    call_id=uuid_mod.uuid4(),
                    muted=request.muted,
                )
        except Exception as e:
            logger.warning(f"Failed to record mute event: {e}")

    await session.inbound_queue.put(
        {"type": "mic.set_muted", "muted": request.muted}
    )

    return AudioMuteResponse(accepted=True)
