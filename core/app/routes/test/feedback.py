"""Test feedback endpoint — thin HTTP adapter.

Core logic lives in app.infra.test.feedback.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.test.feedback import create_feedback_impl
from app.infra.test.group import group_test_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class CreateFeedbackApiRequest(BaseModel):
    grade_id: UUID = Field(..., description="Grade entry to attach feedback to")
    tool_call_id: UUID = Field(..., description="Tool call being graded")
    standard_group_id: UUID = Field(..., description="Rubric standard group being scored")
    score: int = Field(0, description="Score for this criterion (1-5)")
    feedback: str = Field("", description="Feedback text")
    run_id: UUID | None = Field(None, description="Run ID for audit linkage")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior call instead of re-running")


@router.post("/feedback")
async def create_feedback(
    request: CreateFeedbackApiRequest,
    http_request: Request,
    response: Response,
) -> dict:
    """Create test feedback for a specific tool call."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID required.")
        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID required.")

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_test_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> dict:
            return await create_feedback_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                grade_id=request.grade_id,
                tool_call_id=request.tool_call_id,
                standard_group_id=request.standard_group_id,
                score=request.score,
                feedback=request.feedback,
                run_id=request.run_id,
            )

        result = await run_artifact_operation_with_audit(
            pool, redis,
            artifact="test",
            operation="feedback",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
        )

        response.headers["X-Invalidate-Tags"] = "test,tests,feedbacks"
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e, route_path=http_request.url.path,
            operation="create_feedback", sql_query=None,
            sql_params=None, request=http_request,
        )
