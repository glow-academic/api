"""Home refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.attempt.group import group_attempt_impl
from app.infra.home_refresh import refresh_home_client
from app.infra.refresh.types import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def home_refresh(
    http_request: Request,
    response: Response,
) -> RefreshResponse:
    """Refresh home materialized views and invalidate caches."""
    pool = get_pool()
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    async def _runner() -> RefreshResponse:
        return await refresh_home_client(
            pool,
            redis,
            profile_id=profile_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="home_refresh",
        arguments={},
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)
    return result
