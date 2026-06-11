"""Chat hints — create hint items for a chat message.

POST /attempt/chat/hints — canonical: idempotency replay + soft/accept
(stage-inactive) via the shared chat-analysis write helper. Hints key on
message_id (no grade lookup).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.attempt.chat_analysis_common import run_chat_analysis_write
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
    soft: bool = False
    accept: bool | None = None


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
    profile_id = UUID(str(profile_id))
    session_id = UUID(str(session_id))
    pool = get_pool()
    redis = get_redis_client()

    async def _create(conn: asyncpg.Connection, r: Redis, soft: bool) -> dict[str, list[UUID]]:
        ids: list[UUID] = []
        for item in request.hints:
            if not item.message_id:
                raise HTTPException(status_code=400, detail="message_id is required for each hint")
            result = await create_attempt_hint(
                conn, r, message_id=item.message_id, session_id=session_id,
                hint=item.hint, soft=soft,
            )
            ids.append(result.id)
        return {"attempt_hint_entry": ids}

    result = await run_chat_analysis_write(
        pool, redis,
        operation="chat_hints",
        primary_table="attempt_hint_entry",
        mv_target="attempt_hint_mv",
        profile_id=profile_id, session_id=session_id, chat_id=request.chat_id,
        idempotency_key=request.idempotency_key, soft=request.soft, accept=request.accept,
        arguments=request.model_dump(mode="json"),
        create_fn=_create,
    )
    return ChatHintsResponse(
        success=True, hint_ids=result.primary_ids, idempotency_key=result.idempotency_key,
    )
