"""Chat analyses — create analysis items for a graded chat.

POST /attempt/chat/analyses
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_grade.search import search_attempt_grades

router = APIRouter()


class ChatAnalysisItem(BaseModel):
    content: str


class ChatAnalysesRequest(BaseModel):
    chat_id: UUID
    analyses: list[ChatAnalysisItem]
    idempotency_key: UUID | None = None
    accept: bool = True


class ChatAnalysesResponse(BaseModel):
    success: bool
    analysis_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/analyses", response_model=ChatAnalysesResponse)
async def chat_analyses(
    request: ChatAnalysesRequest,
    http_request: Request,
) -> ChatAnalysesResponse:
    """Create analysis items for the latest grade on a chat."""
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

        analysis_ids: list[UUID] = []
        for item in request.analyses:
            result = await create_attempt_analysis(
                conn,
                grade_id=grade_id,
                session_id=session_id,
                content=item.content,
                soft=not request.accept,
            )
            analysis_ids.append(result.id)

    return ChatAnalysesResponse(
        success=True,
        analysis_ids=analysis_ids,
        idempotency_key=request.idempotency_key,
    )
