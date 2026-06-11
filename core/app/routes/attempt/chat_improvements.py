"""Chat improvements — create improvement items with optional inline replacements.

POST /attempt/chat/improvements — canonical: idempotency replay + soft/accept
(stage-inactive) via the shared chat-analysis write helper. Both the improvement
rows AND their child replacement rows are staged/activated together.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.attempt.chat_analysis_common import run_chat_analysis_write
from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.attempt_grade.search import search_attempt_grades
from app.tools.entries.attempt_improvement.create import create_attempt_improvement
from app.tools.entries.attempt_replacement.create import create_attempt_replacement

router = APIRouter()


class ChatReplacementItem(BaseModel):
    section: str
    replace: str
    idx: int | None = None


class ChatImprovementItem(BaseModel):
    name: str
    description: str
    message_id: UUID | None = None
    replacements: list[ChatReplacementItem] | None = None


class ChatImprovementsRequest(BaseModel):
    chat_id: UUID
    improvements: list[ChatImprovementItem]
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatImprovementsResponse(BaseModel):
    success: bool
    improvement_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/chat_improvements", response_model=ChatImprovementsResponse)
async def chat_improvements(
    request: ChatImprovementsRequest,
    http_request: Request,
) -> ChatImprovementsResponse:
    """Create improvement items (with optional inline replacements) for the latest grade."""
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
        improvement_ids: list[UUID] = []
        replacement_ids: list[UUID] = []
        for item in request.improvements:
            result = await create_attempt_improvement(
                conn, r, grade_id=grade_id, message_id=item.message_id or uuid4(),
                session_id=session_id, name=item.name, description=item.description, soft=soft,
            )
            improvement_ids.append(result.id)
            for rpl in item.replacements or []:
                rpl_row = await create_attempt_replacement(
                    conn, r, improvement_id=result.id, session_id=session_id,
                    section=rpl.section, replace=rpl.replace, idx=rpl.idx or 0, soft=soft,
                )
                replacement_ids.append(rpl_row.id)
        rows: dict[str, list[UUID]] = {"attempt_improvement_entry": improvement_ids}
        if replacement_ids:
            rows["attempt_replacement_entry"] = replacement_ids
        return rows

    result = await run_chat_analysis_write(
        pool, redis,
        operation="chat_improvements",
        primary_table="attempt_improvement_entry",
        mv_target="attempt_improvement_mv",
        profile_id=profile_id, session_id=session_id, chat_id=request.chat_id,
        idempotency_key=request.idempotency_key, soft=request.soft, accept=request.accept,
        arguments=request.model_dump(mode="json"),
        create_fn=_create,
    )
    return ChatImprovementsResponse(
        success=True, improvement_ids=result.primary_ids, idempotency_key=result.idempotency_key,
    )
