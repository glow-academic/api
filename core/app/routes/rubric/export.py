"""Rubric export endpoint — PDF generation.

Returns a raw PDF (`application/pdf`) for the requested rubric,
optionally filled with per-standard highlights + feedback when
`grade_id` is supplied. Thin wrapper over `export_rubric_impl` — the
infra layer produces the canonical `ExportRubricApiResponse` envelope
(base64 PDF, used by the websocket path too); this route decodes it
back to raw bytes for HTTP delivery.
"""

import base64
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.infra.globals import get_pool, get_redis_client
from app.infra.rubric.export import export_rubric_impl

router = APIRouter()


class ExportRubricApiRequest(BaseModel):
    """Request model for rubric export."""

    rubric_id: UUID = Field(..., description="Rubric UUID to export")
    grade_id: UUID | None = Field(
        None,
        description=(
            "Optional grade UUID. When provided, the PDF highlights "
            "achieved/passed standards and renders per-standard feedback. "
            "Without it, an empty rubric template is returned."
        ),
    )


@router.post(
    "/export",
    responses={200: {"content": {"application/pdf": {}}}},
    response_class=Response,
)
async def export_rubrics(
    body: ExportRubricApiRequest,
    http_request: Request,
) -> Response:
    """Export a rubric as a PDF (optionally filled with grade data)."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    envelope = await export_rubric_impl(
        pool,
        redis,
        profile_id=profile_id,
        rubric_id=body.rubric_id,
        grade_id=body.grade_id,
    )

    pdf_bytes = base64.b64decode(envelope.content)

    # RFC 5987-encoded filename so non-ASCII rubric names survive the
    # Content-Disposition header round-trip (most browsers honor
    # `filename*=UTF-8''…`, falling back to `filename="…"`).
    fallback = envelope.file_name.encode("ascii", errors="replace").decode("ascii")
    encoded = quote(envelope.file_name, safe="")
    return Response(
        content=pdf_bytes,
        media_type=envelope.mime_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'
            ),
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
