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
from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.rubric.export import export_rubric_impl
from app.infra.rubric.group import group_rubric_impl
from app.infra.rubric.types import ExportRubricApiResponse

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
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")
    soft: bool = Field(False, description="Stage the export dormant (active=False); ack with accept activates it")
    accept: bool | None = Field(None, description="Ack: True promotes the staged export, False rejects. Only meaningful with idempotency_key")


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

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_rubric_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = body.accept is not None and body.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ExportRubricApiResponse:
        return await export_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            rubric_id=body.rubric_id,
            chat_id=body.chat_id,
            soft=body.soft,
            accept=body.accept,
            idempotency_key=body.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="rubric",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
        response_model=ExportRubricApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
