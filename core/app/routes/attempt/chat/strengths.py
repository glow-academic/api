"""Chat strengths — create strength items with optional inline highlights.

POST /attempt/chat/strengths
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
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
    highlights: list[ChatHighlightItem] | None = None


class ChatStrengthsRequest(BaseModel):
    chat_id: UUID
    strengths: list[ChatStrengthItem]
    idempotency_key: UUID | None = None
    accept: bool = True


class ChatStrengthsResponse(BaseModel):
    success: bool
    strength_ids: list[UUID]
    idempotency_key: UUID | None = None


@router.post("/strengths", response_model=ChatStrengthsResponse)
async def chat_strengths(
    request: ChatStrengthsRequest,
    http_request: Request,
) -> ChatStrengthsResponse:
    """Create strength items (with optional inline highlights) for the latest grade."""
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

        strength_ids: list[UUID] = []
        for item in request.strengths:
            result = await create_attempt_strength(
                conn,
                grade_id=grade_id,
                message_id=item.message_id or uuid4(),
                session_id=session_id,
                name=item.name,
                description=item.description,
                soft=not request.accept,
            )
            strength_ids.append(result.id)

            # Create inline highlights as children
            if item.highlights:
                for hl in item.highlights:
                    await create_attempt_highlight(
                        conn,
                        strength_id=result.id,
                        session_id=session_id,
                        section=hl.section,
                        idx=hl.idx or 0,
                        soft=not request.accept,
                    )

    return ChatStrengthsResponse(
        success=True,
        strength_ids=strength_ids,
        idempotency_key=request.idempotency_key,
    )
