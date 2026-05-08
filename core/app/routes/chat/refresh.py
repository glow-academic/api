"""Chat refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.attempt.chat.refresh import RefreshChatApiRequest, refresh_chat_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.refresh.types import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def chat_refresh(
    request: RefreshChatApiRequest,
    http_request: Request,
    response: Response,
) -> RefreshResponse:
    """Refresh chat materialized views and invalidate caches."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    async def _runner() -> RefreshResponse:
        return await refresh_chat_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            request=request,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="chat_refresh",
        arguments=request.model_dump(mode="json"),
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)
    return result
