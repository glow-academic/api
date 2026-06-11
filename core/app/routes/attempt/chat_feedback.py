"""Chat feedback — create feedback items for a graded chat.

POST /attempt/chat/feedback — canonical: idempotency replay + soft/accept
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
from app.tools.entries.attempt_feedback.create import create_attempt_feedback
from app.tools.entries.attempt_grade.search import search_attempt_grades

router = APIRouter()


class ChatFeedbackItem(BaseModel):
    feedback: str
    total: float | None = None


class ChatFeedbackRequest(BaseModel):
    chat_id: UUID
    feedbacks: list[ChatFeedbackItem]
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatFeedbackResponse(BaseModel):
    success: bool
    feedback_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/chat_feedback", response_model=ChatFeedbackResponse)
async def chat_feedback(
    request: ChatFeedbackRequest,
    http_request: Request,
) -> ChatFeedbackResponse:
    """Create feedback items for the latest grade on a chat."""
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
        for item in request.feedbacks:
            result = await create_attempt_feedback(
                conn, r, grade_id=grade_id, session_id=session_id,
                total=int(item.total) if item.total is not None else 0,
                feedback=item.feedback, soft=soft,
            )
            ids.append(result.id)
        return {"attempt_feedback_entry": ids}

    result = await run_chat_analysis_write(
        pool, redis,
        operation="chat_feedback",
        primary_table="attempt_feedback_entry",
        mv_target="attempt_feedback_mv",
        profile_id=profile_id, session_id=session_id, chat_id=request.chat_id,
        idempotency_key=request.idempotency_key, soft=request.soft, accept=request.accept,
        arguments=request.model_dump(mode="json"),
        create_fn=_create,
    )
    return ChatFeedbackResponse(
        success=True, feedback_ids=result.primary_ids, idempotency_key=result.idempotency_key,
    )
