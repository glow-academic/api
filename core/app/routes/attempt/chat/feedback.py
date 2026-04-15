"""Chat feedback — create feedback items for a graded chat.

POST /attempt/chat/feedback
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
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
    accept: bool = True


class ChatFeedbackResponse(BaseModel):
    success: bool
    feedback_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/feedback", response_model=ChatFeedbackResponse)
async def chat_feedback(
    request: ChatFeedbackRequest,
    http_request: Request,
) -> ChatFeedbackResponse:
    """Create feedback items for the latest grade on a chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    async with pool.acquire() as conn:
        grades = await search_attempt_grades(conn, chat_ids=[request.chat_id], limit=1)
        if not grades:
            raise HTTPException(status_code=404, detail="No grade found for this chat")
        grade_id = grades[0].grade_id

        call_id = uuid4()
        feedback_ids: list[UUID] = []
        for item in request.feedbacks:
            result = await create_attempt_feedback(
                conn,
                grade_id=grade_id,
                call_id=call_id,
                total=int(item.total) if item.total is not None else 0,
                feedback=item.feedback,
                soft=not request.accept,
            )
            feedback_ids.append(result.id)

    return ChatFeedbackResponse(
        success=True,
        feedback_ids=feedback_ids,
        idempotency_key=request.idempotency_key,
    )
