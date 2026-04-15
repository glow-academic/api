"""Profile problem endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.profile.problem.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.group import group_profile_impl
from app.infra.profile.problem import problem_profile_impl
from app.infra.profile.types import (
    ProblemProfileApiRequest,
    ProblemProfileApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/problem", response_model=ProblemProfileApiResponse)
async def problem_profile(
    request: ProblemProfileApiRequest,
    http_request: Request,
    response: Response,
) -> ProblemProfileApiResponse:
    """Report a profile problem — composable infra architecture."""
    tags = ["profiles", "problems"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        group_result = await group_profile_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

        async def _runner() -> ProblemProfileApiResponse:
            return await problem_profile_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                type=request.type,
                message=request.message,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="problem",
            arguments=request.model_dump(mode="json"),
            response_model=ProblemProfileApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="problem_profile",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
