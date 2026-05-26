"""Chat analyses — create analysis items for a graded chat.

POST /attempt/chat/analyses — canonical: idempotency replay + soft/accept
(stage-inactive) via the shared chat-analysis write helper.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.attempt.chat_analysis_common import run_chat_analysis_write
from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_grade.search import search_attempt_grades

router = APIRouter()


class ChatAnalysisItem(BaseModel):
    content: str


class ChatAnalysesRequest(BaseModel):
    chat_id: UUID
    analyses: list[ChatAnalysisItem]
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatAnalysesResponse(BaseModel):
    success: bool
    analysis_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/chat_analyses", response_model=ChatAnalysesResponse)
async def chat_analyses(
    request: ChatAnalysesRequest,
    http_request: Request,
) -> ChatAnalysesResponse:
    """Create analysis items for the latest grade on a chat."""
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
        ids: list[UUID] = []
        for item in request.analyses:
            result = await create_attempt_analysis(
                conn, r, grade_id=grade_id, session_id=session_id,
                content=item.content, soft=soft,
            )
            ids.append(result.id)
        return {"attempt_analysis_entry": ids}

    result = await run_chat_analysis_write(
        pool, redis,
        operation="chat_analyses",
        primary_table="attempt_analysis_entry",
        mv_target="attempt_analysis_mv",
        profile_id=profile_id, session_id=session_id,
        idempotency_key=request.idempotency_key, soft=request.soft, accept=request.accept,
        arguments=request.model_dump(mode="json"),
        create_fn=_create,
    )
    return ChatAnalysesResponse(
        success=True, analysis_ids=result.primary_ids, idempotency_key=result.idempotency_key,
    )
