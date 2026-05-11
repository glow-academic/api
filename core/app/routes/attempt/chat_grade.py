"""Chat grade — trigger grading for an attempt chat.

Manual-grade HTTP entry point. Shares `chat_grade_attempt_impl` with the
LLM tool (Attempt_Chat_Grade), so manual and AI grading go through the
same code path.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.infra.attempt.chat_grade import chat_grade_attempt_impl
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class GradeAttemptApiRequest(BaseModel):
    chat_id: UUID = Field(..., description="UUID of the attempt chat to grade")
    score: int = Field(..., description="Overall score to record for the chat")


class GradeAttemptApiResponse(BaseModel):
    chat_id: str
    grade_id: str | None = None
    score: int | None = None
    passed: bool | None = None
    time_taken: int | None = None


@router.post("/chat_grade", response_model=GradeAttemptApiResponse)
async def chat_grade(
    request: GradeAttemptApiRequest,
    http_request: Request,
) -> GradeAttemptApiResponse:
    """Manually grade an attempt chat with a score."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await chat_grade_attempt_impl(
            get_pool(),
            get_redis_client(),
            profile_id=UUID(str(profile_id)),
            session_id=UUID(str(session_id)),
            chat_id=request.chat_id,
            score=request.score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GradeAttemptApiResponse(
        chat_id=str(result["chat_id"]),
        grade_id=str(result["grade_id"]) if result.get("grade_id") else None,
        score=result.get("score"),
        passed=result.get("passed"),
        time_taken=result.get("time_taken"),
    )
