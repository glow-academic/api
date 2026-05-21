"""Persona refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.persona.group import group_persona_impl
from app.infra.persona.refresh import refresh_persona_impl
from app.infra.refresh.types import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def persona_refresh(
    http_request: Request,
    response: Response,
) -> RefreshResponse:
    """Refresh persona materialized views and invalidate caches."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> RefreshResponse:
        return await refresh_persona_impl(
            pool,
            redis,
            profile_id=profile_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="persona",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="refresh",
        arguments={},
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )

    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)

    return result
