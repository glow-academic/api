"""Cohort export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.infra.cohort.export import export_cohort_impl
from app.infra.cohort.types import ExportCohortApiResponse
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


class ExportCohortApiRequest(BaseModel):
    """Request model for cohort export."""

    cohort_id: UUID | None = None


@router.post("/export", response_model=ExportCohortApiResponse)
async def export_cohorts(
    body: ExportCohortApiRequest,
    http_request: Request,
) -> ExportCohortApiResponse:
    """Export all cohorts as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_cohort_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        cohort_id=body.cohort_id,
    )
