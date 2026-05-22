"""Parameter export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.parameter.export import export_parameter_impl
from app.infra.parameter.group import group_parameter_impl
from app.infra.parameter.types import (
    ExportParameterApiRequest,
    ExportParameterApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportParameterApiResponse)
async def export_parameters(
    body: ExportParameterApiRequest,
    http_request: Request,
) -> ExportParameterApiResponse:
    """Export all parameters as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_parameter_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> ExportParameterApiResponse:
        return await export_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            parameter_id=body.parameter_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="parameter",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments=body.model_dump(mode="json"),
        response_model=ExportParameterApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
