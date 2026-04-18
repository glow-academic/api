"""Chat complete — mark an attempt chat as completed.

POST /attempt/chat/complete
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.chat_complete import chat_complete_attempt_impl
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class ChatCompleteRequest(BaseModel):
    chat_id: UUID
    message: str = ""


class ChatCompleteResponse(BaseModel):
    success: bool
    completion_id: str
    chat_id: str


@router.post("/complete", response_model=ChatCompleteResponse)
async def chat_complete(
    request: ChatCompleteRequest,
    http_request: Request,
) -> ChatCompleteResponse:
    """Mark an attempt chat as completed — final step after grading."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    redis = get_redis_client()

    try:
        result = await chat_complete_attempt_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            chat_id=request.chat_id,
            message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatCompleteResponse(
        success=True,
        completion_id=result["completion_id"],
        chat_id=result["chat_id"],
    )
