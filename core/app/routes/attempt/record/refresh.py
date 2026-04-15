"""Record refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.record.group import group_record_impl
from app.infra.record_refresh import refresh_record_client
from app.infra.refresh.types import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def record_refresh(
    http_request: Request,
    response: Response,
) -> RefreshResponse:
    """Refresh record caches."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_record_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    async def _runner() -> RefreshResponse:
        return await refresh_record_client(
            pool,
            redis,
            profile_id=profile_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="record",
        profile_id=profile_id,
        session_id=session_id,
        operation="refresh",
        arguments={},
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        group_id=group_id,
    )
    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)
    return result
