"""Chat message — create a message in an attempt chat.

POST /attempt/chat/message

Pure data primitive. Creates attempt_message_entry + attempt_content_entry.
No AI, no voice routing. Audio and generation go through separate endpoints.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.message import (
    AttemptMessageInternalResult,
    attempt_message_internal_impl,
)
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class ChatMessageRequest(BaseModel):
    chat_id: UUID
    text: str
    persona_id: UUID | None = None
    parent_message_id: UUID | None = None


class ChatMessageResponse(BaseModel):
    success: bool
    message_id: str
    content_ids: list[str]


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    request: ChatMessageRequest,
    http_request: Request,
) -> ChatMessageResponse:
    """Create a message in an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    redis = get_redis_client()

    try:
        result = await attempt_message_internal_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            chat_id=request.chat_id,
            text=request.text,
            persona_id=request.persona_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatMessageResponse(
        success=result.success,
        message_id=result.message_id or "",
        content_ids=result.content_ids,
    )
