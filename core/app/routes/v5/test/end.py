"""Test end endpoint — end a single invocation within a test.

Synchronous equivalent of socket event: test_end.

When grade=True (default), triggers the grading pipeline. An agent can
optionally provide pre-computed grade data to skip the internal AI.

TODO: Wire to actual infra (end invocation, optionally trigger or skip grading).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.test.end import test_end_internal_impl

router = APIRouter()


class EndTestApiRequest(BaseModel):
    test_id: UUID
    test_invocation_id: UUID
    run_id: UUID
    grade: bool = True
    # Optional — agent can provide these, otherwise internal AI generates them
    score: float | None = None
    passed: bool | None = None
    feedback: str | None = None


class EndTestApiResponse(BaseModel):
    invocation_id: str
    grade_id: str | None = None
    score: float | None = None
    passed: bool | None = None
    feedback: str | None = None


@router.post("/end", response_model=EndTestApiResponse)
async def end_test(
    request: EndTestApiRequest,
    http_request: Request,
) -> EndTestApiResponse:
    """End a single invocation within a test.

    Browser client: sends grade=True, internal AI generates grade + feedback.
    Agent: can optionally provide score, passed, feedback to skip AI.
    """
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await test_end_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EndTestApiResponse.model_validate(result.model_dump(mode="json"))
