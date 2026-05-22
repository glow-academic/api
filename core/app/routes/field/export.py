"""Field export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.export import export_field_impl
from app.infra.field.group import group_field_impl
from app.infra.field.types import ExportFieldApiRequest, ExportFieldApiResponse
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/export", response_model=ExportFieldApiResponse)
async def export_fields(
    body: ExportFieldApiRequest,
    http_request: Request,
) -> ExportFieldApiResponse:
    """Export all fields as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_field_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> ExportFieldApiResponse:
        return await export_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            field_id=body.field_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="field",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments=body.model_dump(mode="json"),
        response_model=ExportFieldApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
