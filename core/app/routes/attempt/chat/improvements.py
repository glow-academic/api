"""Chat improvements — create improvement items with optional inline replacements.

POST /attempt/chat/improvements
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
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
    accept: bool = True


class ChatImprovementsResponse(BaseModel):
    success: bool
    improvement_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/improvements", response_model=ChatImprovementsResponse)
async def chat_improvements(
    request: ChatImprovementsRequest,
    http_request: Request,
) -> ChatImprovementsResponse:
    """Create improvement items (with optional inline replacements) for the latest grade."""
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
        improvement_ids: list[UUID] = []
        for item in request.improvements:
            result = await create_attempt_improvement(
                conn,
                grade_id=grade_id,
                message_id=item.message_id or uuid4(),
                call_id=call_id,
                name=item.name,
                description=item.description,
                soft=not request.accept,
            )
            improvement_ids.append(result.id)

            # Create inline replacements as children
            if item.replacements:
                for rpl in item.replacements:
                    await create_attempt_replacement(
                        conn,
                        improvement_id=result.id,
                        call_id=call_id,
                        section=rpl.section,
                        replace=rpl.replace,
                        idx=rpl.idx or 0,
                        soft=not request.accept,
                    )

    return ChatImprovementsResponse(
        success=True,
        improvement_ids=improvement_ids,
        idempotency_key=request.idempotency_key,
    )
