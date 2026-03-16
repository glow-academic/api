"""Attempt grade endpoint — trigger grading for an attempt chat.

Equivalent of socket event: attempt_grade.

When called by a browser client, only attempt_id/chat_id is provided — the
internal AI generates grade, feedback, strengths, improvements, analyses,
highlights, and replacements.

When called by an agent, optional fields allow providing pre-computed results.
If optional fields are omitted, the internal AI pipeline runs as normal.

TODO: Wire to actual infra (trigger or skip grading pipeline).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.grade_types import (
    GradeAttemptRequest,
)
from app.infra.attempt.grade import attempt_grade_internal_impl

router = APIRouter()


class GradeAttemptApiResponse(BaseModel):
    chat_id: str
    grade_id: str | None = None
    score: int | None = None
    passed: bool | None = None


@router.post("/grade", response_model=GradeAttemptApiResponse)
async def attempt_grade(
    request: GradeAttemptRequest,
    http_request: Request,
) -> GradeAttemptApiResponse:
    """Trigger grading for an attempt chat.

    Browser client: sends chat_id only, internal AI generates full grade.
    Agent: can optionally provide score, feedbacks, strengths, etc. to skip AI.
    """
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_grade_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GradeAttemptApiResponse.model_validate(result.model_dump(mode="json"))
