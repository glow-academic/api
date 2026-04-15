"""Chat mute — toggle microphone mute for a voice session.

Was: POST /attempt/audio/mute
Now: POST /attempt/chat/mute
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


class ChatMuteRequest(BaseModel):
    chat_id: UUID
    muted: bool = False


class ChatMuteResponse(BaseModel):
    accepted: bool


@router.post("/mute", response_model=ChatMuteResponse)
async def chat_mute(
    request: ChatMuteRequest,
    http_request: Request,
) -> ChatMuteResponse:
    """Toggle microphone mute for a voice session."""
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

    return ChatMuteResponse(accepted=True)
