"""Auth export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.auth.export import export_auth_impl
from app.infra.auth.group import group_auth_impl
from app.infra.auth.types import ExportAuthApiRequest, ExportAuthApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/export", response_model=ExportAuthApiResponse)
async def export_auths(
    body: ExportAuthApiRequest,
    http_request: Request,
) -> ExportAuthApiResponse:
    """Export all auths as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_auth_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> ExportAuthApiResponse:
        return await export_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            auth_id=body.auth_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="auth",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments=body.model_dump(mode="json"),
        response_model=ExportAuthApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
