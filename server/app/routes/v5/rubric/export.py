"""Rubric export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.rubric.export import export_rubric_impl
from app.infra.rubric.types import ExportRubricApiResponse

router = APIRouter()


class ExportRubricApiRequest(BaseModel):
    """Request model for rubric export."""

    rubric_id: UUID | None = None


@router.post("/export", response_model=ExportRubricApiResponse)
async def export_rubrics(
    body: ExportRubricApiRequest,
    http_request: Request,
) -> ExportRubricApiResponse:
    """Export all rubrics as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_rubric_impl(
        pool,
        redis,
        profile_id=profile_id,
        rubric_id=body.rubric_id,
    )
