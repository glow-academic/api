"""Problem create endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.activity.problem import problem_activity_impl
from app.infra.activity.types import CreateProblemApiRequest, CreateProblemApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/problem", response_model=CreateProblemApiResponse, tags=["activity"])
async def create_problem(
    request: CreateProblemApiRequest,
    http_request: Request,
    response: Response,
) -> CreateProblemApiResponse:
    """Create new problem entry."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateProblemApiResponse:
            return await problem_activity_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                type=request.type,
                message=request.message,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="activity",
            operation="problem",
            profile_id=profile_id,
            session_id=session_id,
            arguments=request.model_dump(mode="json"),
            response_model=CreateProblemApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "problems,views,activity"
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_problem",
            request=http_request,
        )
