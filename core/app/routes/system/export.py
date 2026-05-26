"""System export endpoint — view-aware, canonical file-modality output.

Routed through the audit wrapper: idempotency replay (operation_key) + soft/accept
staging of the dormant export file chain (propose → accept activates).
"""

from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.export import export_system_impl
from app.infra.system.group import group_system_impl
from app.infra.system.types import ExportSystemApiRequest, ExportSystemApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportSystemApiResponse)
async def export_system(
    body: ExportSystemApiRequest,
    http_request: Request,
    response: Response,
) -> ExportSystemApiResponse:
    """Artifact-level system export.

    Dispatches on ``body.view`` to per-view exports (activity, pricing,
    group, session, health) and returns ``{file_id, file_name, row_count}``.
    Client downloads via ``/api/system/download/{file_id}`` (BFF) →
    ``/system/file/download``.
    """
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking.
    group_id = None
    if session_id:
        group_result = await group_system_impl(
            pool, redis, profile_id=UUID(str(profile_id)), session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = body.accept is not None and body.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ExportSystemApiResponse:
        return await export_system_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            view=body.view,
            target_session_id=body.session_id,
            group_id=body.group_id,
            mode=body.mode,
            soft=body.soft,
            accept=body.accept,
            idempotency_key=body.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="system",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
        operation_key=body.idempotency_key,  # idempotency replay gate
        response_model=ExportSystemApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
