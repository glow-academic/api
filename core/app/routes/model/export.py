"""Model export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.model.export import export_model_impl
from app.infra.model.group import group_model_impl
from app.infra.model.types import ExportModelApiRequest, ExportModelApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportModelApiResponse)
async def export_models(
    body: ExportModelApiRequest,
    http_request: Request,
) -> ExportModelApiResponse:
    """Export all models as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_model_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = body.accept is not None and body.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ExportModelApiResponse:
        return await export_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            model_id=body.model_id,
            soft=body.soft,
            accept=body.accept,
            idempotency_key=body.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="model",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
        response_model=ExportModelApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
