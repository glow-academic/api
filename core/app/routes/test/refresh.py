"""Test refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.refresh.types import RefreshApiRequest, RefreshResponse
from app.infra.test.group import group_test_impl
from app.infra.test.refresh import refresh_test_impl

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def test_refresh(
    http_request: Request,
    response: Response,
    request: RefreshApiRequest | None = None,
) -> RefreshResponse:
    """Refresh test materialized views and invalidate caches."""
    req = request or RefreshApiRequest()
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()

    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_test_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    is_ack = req.accept is not None and req.idempotency_key is not None

    async def _runner() -> RefreshResponse:
        return await refresh_test_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=req.soft,
            accept=req.accept,
            idempotency_key=req.idempotency_key,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="refresh",
        test_id=None,
        arguments={"accept": req.accept} if is_ack else req.model_dump(mode="json"),
        operation_key=req.idempotency_key,  # idempotency replay gate
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )

    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)

    return result
