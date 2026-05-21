"""Chat hints — create hint items for a chat message.

POST /attempt/chat/hints
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.attempt_hint.create import create_attempt_hint

router = APIRouter()


class ChatHintItem(BaseModel):
    hint: str
    message_id: UUID | None = None
    idx: int | None = None


class ChatHintsRequest(BaseModel):
    chat_id: UUID
    hints: list[ChatHintItem]
    idempotency_key: UUID | None = None
    accept: bool = True


class ChatHintsResponse(BaseModel):
    success: bool
    hint_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/chat_hints", response_model=ChatHintsResponse)
async def chat_hints(
    request: ChatHintsRequest,
    http_request: Request,
) -> ChatHintsResponse:
    """Create hint items for messages in a chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    if not request.hints:
        raise HTTPException(status_code=400, detail="At least one hint is required")

    pool = get_pool()
    async with pool.acquire() as conn:
        hint_ids: list[UUID] = []
        for item in request.hints:
            if not item.message_id:
                raise HTTPException(
                    status_code=400,
                    detail="message_id is required for each hint",
                )
            result = await create_attempt_hint(
                conn, get_redis_client(),
                message_id=item.message_id,
                session_id=session_id,
                hint=item.hint,
                soft=not request.accept,
            )
            hint_ids.append(result.id)

    return ChatHintsResponse(
        success=True,
        hint_ids=hint_ids,
        idempotency_key=request.idempotency_key,
    )
