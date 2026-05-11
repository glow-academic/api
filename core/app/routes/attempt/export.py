"""Attempt export endpoint — view-aware, canonical file-modality output."""

from fastapi import APIRouter, Request, Response

from app.infra.attempt.export import export_attempt_impl
from app.infra.attempt.types import ExportAttemptApiRequest, ExportAttemptApiResponse
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


@router.post("/export", response_model=ExportAttemptApiResponse)
async def export_attempt(
    body: ExportAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> ExportAttemptApiResponse:
    """Artifact-level attempt export.

    Dispatches on ``body.view`` to per-view exports and returns
    ``{file_id, file_name, row_count}``. Client downloads via
    ``/api/attempt/download/{file_id}`` (BFF) → ``/attempt/file/download``.
    """
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_attempt_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        view=body.view,
        attempt_id=body.attempt_id,
        record_id=body.record_id,
        mode=body.mode,
    )
