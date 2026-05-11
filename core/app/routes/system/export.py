"""System export endpoint — view-aware, canonical file-modality output."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.system.export import export_system_impl
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

    return await export_system_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        view=body.view,
        target_session_id=body.session_id,
        group_id=body.group_id,
    )
