"""Problem resolve endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.activity.resolve import resolve_activity_impl
from app.infra.activity.types import ResolveProblemApiRequest, ResolveProblemApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.group import group_system_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/resolve", response_model=ResolveProblemApiResponse)
async def resolve_problem(
    request: ResolveProblemApiRequest,
    http_request: Request,
    response: Response,
) -> ResolveProblemApiResponse:
    """Resolve or unresolve a problem entry."""
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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> ResolveProblemApiResponse:
            return await resolve_activity_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                problem_id=request.problem_id,
                resolved=request.resolved,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="system",
            operation="activity_resolve",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            response_model=ResolveProblemApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "problems,views,activity,summary"
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="resolve_problem",
            request=http_request,
        )
