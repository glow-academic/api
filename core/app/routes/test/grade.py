"""Test grade endpoint — thin HTTP adapter.

Core logic lives in app.infra.test.grade.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.test.grade import create_grade_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class CreateGradeApiRequest(BaseModel):
    invocation_id: UUID = Field(..., description="Test invocation to grade")
    run_id: UUID | None = Field(None, description="Run ID for audit linkage")
    score: int = Field(0, description="Overall score")


@router.post("/grade")
async def create_grade(
    request: CreateGradeApiRequest,
    http_request: Request,
    response: Response,
) -> dict:
    """Create a test grade."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID required.")
        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID required.")

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> dict:
            return await create_grade_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                invocation_id=request.invocation_id,
                run_id=request.run_id,
                score=request.score,
            )

        result = await run_artifact_operation_with_audit(
            pool, redis,
            artifact="test",
            operation="grade",
            profile_id=profile_id,
            session_id=session_id,
            arguments=request.model_dump(mode="json"),
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "test,tests,grades"
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e, route_path=http_request.url.path,
            operation="create_grade", sql_query=None,
            sql_params=None, request=http_request,
        )
