"""Test export endpoint — view-aware, canonical file-modality output."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.test.export import export_test_impl
from app.infra.test.types import ExportTestApiRequest, ExportTestApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportTestApiResponse)
async def export_test(
    body: ExportTestApiRequest,
    http_request: Request,
    response: Response,
) -> ExportTestApiResponse:
    """Artifact-level test export.

    Dispatches on ``body.view`` to per-view exports and returns
    ``{file_id, file_name, row_count}``. Client downloads via
    ``/api/test/download/{file_id}`` (BFF) → ``/test/file/download``.
    """
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()

    return await export_test_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
        view=body.view,
        test_id=body.test_id,
        invocation_id=body.invocation_id,
        draft_id=body.draft_id,
    )
