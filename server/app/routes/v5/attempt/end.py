"""Attempt end endpoint — end a single chat within an attempt.

Synchronous equivalent of socket event: attempt_end.

When grade=True (default), triggers the grading pipeline. An agent can
optionally provide pre-computed grade data to skip the internal AI.

TODO: Wire to actual infra (end chat, optionally trigger or skip grading).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.infra.attempt.grade_types import (
    AttemptGradeAnalysisEntry,
    AttemptGradeFeedbackEntry,
    AttemptGradeHighlightEntry,
    AttemptGradeImprovementEntry,
    AttemptGradeReplacementEntry,
    AttemptGradeStrengthEntry,
)
from app.infra.attempt.end import attempt_end_internal_impl

router = APIRouter()


class EndAttemptApiRequest(BaseModel):
    attempt_id: UUID = Field(..., description="UUID of the attempt to end")
    chat_id: UUID = Field(..., description="UUID of the chat to end")
    grade: bool = Field(True, description="Whether to trigger grading after ending")
    # Optional — agent can provide these, otherwise internal AI generates them
    # Only used when grade=True
    score: int | None = Field(None, description="Pre-computed score from the agent")
    passed: bool | None = Field(None, description="Pre-computed pass/fail from the agent")
    time_taken: int | None = Field(None, description="Time taken in seconds")
    feedbacks: list[AttemptGradeFeedbackEntry] | None = Field(None, description="Pre-computed feedback entries")
    strengths: list[AttemptGradeStrengthEntry] | None = Field(None, description="Pre-computed strength entries")
    improvements: list[AttemptGradeImprovementEntry] | None = Field(None, description="Pre-computed improvement entries")
    analyses: list[AttemptGradeAnalysisEntry] | None = Field(None, description="Pre-computed analysis entries")
    highlights: list[AttemptGradeHighlightEntry] | None = Field(None, description="Pre-computed highlight entries")
    replacements: list[AttemptGradeReplacementEntry] | None = Field(None, description="Pre-computed replacement entries")


class EndAttemptApiResponse(BaseModel):
    chat_id: str = Field(..., description="ID of the ended chat")
    is_attempt_finished: bool | None = Field(None, description="Whether the entire attempt is finished")
    grade_id: str | None = Field(None, description="ID of the generated grade")
    score: int | None = Field(None, description="Overall score")
    passed: bool | None = Field(None, description="Whether the attempt passed")


@router.post("/end", response_model=EndAttemptApiResponse)
async def end_attempt(
    request: EndAttemptApiRequest,
    http_request: Request,
) -> EndAttemptApiResponse:
    """End a single chat within an attempt.

    Browser client: sends grade=True, internal AI generates full grade.
    Agent: can optionally provide score, feedbacks, strengths, etc. to skip AI.
    """
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_end_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EndAttemptApiResponse.model_validate(result.model_dump(mode="json"))
