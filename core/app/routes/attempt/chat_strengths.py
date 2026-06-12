"""Chat strengths — create strength items with optional inline highlights.

POST /attempt/chat/strengths — canonical: idempotency replay + soft/accept
(stage-inactive) via the shared chat-analysis write helper. Both the strength
rows AND their child highlight rows are staged/activated together.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.attempt.chat_analysis_common import run_chat_analysis_write
from app.infra.globals import get_pool, get_redis_client
from app.infra.shared_types import MAX_BULK_ITEMS
from app.tools.entries.attempt_grade.search import search_attempt_grades
from app.tools.entries.attempt_highlight.create import create_attempt_highlight
from app.tools.entries.attempt_strength.create import create_attempt_strength

router = APIRouter()


class ChatHighlightItem(BaseModel):
    section: str
    idx: int | None = None


class ChatStrengthItem(BaseModel):
    name: str
    description: str
    message_id: UUID | None = None
    # Bounded (C4-C): each highlight is a per-item DB INSERT inside the grade
    # write transaction; an unbounded array lets one request fan out arbitrarily
    # many round trips / hold a transaction open (resource-exhaustion DoS).
    highlights: list[ChatHighlightItem] | None = Field(None, max_length=MAX_BULK_ITEMS)


class ChatStrengthsRequest(BaseModel):
    chat_id: UUID
    strengths: list[ChatStrengthItem] = Field(..., max_length=MAX_BULK_ITEMS)
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatStrengthsResponse(BaseModel):
    success: bool
    strength_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/chat_strengths", response_model=ChatStrengthsResponse)
async def chat_strengths(
    request: ChatStrengthsRequest,
    http_request: Request,
) -> ChatStrengthsResponse:
    """Create strength items (with optional inline highlights) for the latest grade."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")
    profile_id = UUID(str(profile_id))
    session_id = UUID(str(session_id))
    pool = get_pool()
    redis = get_redis_client()

    async def _create(conn: asyncpg.Connection, r: Redis, soft: bool) -> dict[str, list[UUID]]:
        grades = await search_attempt_grades(conn, r, chat_ids=[request.chat_id], limit=1)
        if not grades:
            raise HTTPException(status_code=404, detail="No grade found for this chat")
        grade_id = grades[0].grade_id
        strength_ids: list[UUID] = []
        highlight_ids: list[UUID] = []
        for item in request.strengths:
            result = await create_attempt_strength(
                conn, r, grade_id=grade_id, message_id=item.message_id or uuid4(),
                session_id=session_id, name=item.name, description=item.description, soft=soft,
            )
            strength_ids.append(result.id)
            for hl in item.highlights or []:
                hl_row = await create_attempt_highlight(
                    conn, r, strength_id=result.id, session_id=session_id,
                    section=hl.section, idx=hl.idx or 0, soft=soft,
                )
                highlight_ids.append(hl_row.id)
        rows: dict[str, list[UUID]] = {"attempt_strength_entry": strength_ids}
        if highlight_ids:
            rows["attempt_highlight_entry"] = highlight_ids
        return rows

    result = await run_chat_analysis_write(
        pool, redis,
        operation="chat_strengths",
        primary_table="attempt_strength_entry",
        mv_target="attempt_strength_mv",
        profile_id=profile_id, session_id=session_id, chat_id=request.chat_id,
        idempotency_key=request.idempotency_key, soft=request.soft, accept=request.accept,
        arguments=request.model_dump(mode="json"),
        create_fn=_create,
    )
    return ChatStrengthsResponse(
        success=True, strength_ids=result.primary_ids, idempotency_key=result.idempotency_key,
    )
