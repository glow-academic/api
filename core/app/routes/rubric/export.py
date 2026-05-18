"""Rubric export endpoint — file-modality PDF export.

Canonical with every other artifact's ``/<art>/export``: the impl
renders the PDF, writes it to disk, and registers it as a
``files_resource`` row. This route returns the JSON envelope
``{file_id, file_name, row_count}``; the client follows up with
``/api/rubric/download/{file_id}`` (BFF over ``/rubric/file/download``)
to fetch the actual bytes. PDF is just another file with
``mime_type='application/pdf'`` — same chain as CSV exports.
"""

from uuid import UUID

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.rubric.export import export_rubric_impl
from app.infra.rubric.types import ExportRubricApiResponse
from pydantic import BaseModel, Field

router = APIRouter()


class ExportRubricApiRequest(BaseModel):
    """Request model for rubric export."""

    rubric_id: UUID = Field(..., description="Rubric UUID to export")
    chat_id: UUID | None = Field(
        None,
        description=(
            "Optional attempt chat UUID. When provided, the PDF "
            "highlights achieved/passed standards and renders "
            "per-standard feedback resolved from the chat's latest "
            "grade. Without it, an empty rubric template is returned."
        ),
    )


@router.post("/export", response_model=ExportRubricApiResponse)
async def export_rubrics(
    body: ExportRubricApiRequest,
    http_request: Request,
) -> ExportRubricApiResponse:
    """Render a rubric PDF and register it as a downloadable file."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_rubric_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        rubric_id=body.rubric_id,
        chat_id=body.chat_id,
    )
