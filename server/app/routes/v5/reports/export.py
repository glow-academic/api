"""Reports export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.reports.export import export_reports_impl
from app.infra.reports.types import ExportReportsApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportReportsApiResponse)
async def export_reports(
    http_request: Request,
    response: Response,
) -> ExportReportsApiResponse:
    """Export all reports data as a clean, denormalized ZIP."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id

    return await export_reports_impl(
        pool,
        redis,
        profile_id=profile_id,
    )
