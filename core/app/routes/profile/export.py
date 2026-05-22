"""Profile export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.export import export_profile_impl
from app.infra.profile.group import group_profile_impl
from app.infra.profile.types import ExportProfileApiRequest, ExportProfileApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportProfileApiResponse)
async def export_profiles(
    body: ExportProfileApiRequest,
    http_request: Request,
) -> ExportProfileApiResponse:
    """Export all profiles as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_profile_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> ExportProfileApiResponse:
        return await export_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            profile_export_id=body.profile_export_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="profile",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments=body.model_dump(mode="json"),
        response_model=ExportProfileApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
