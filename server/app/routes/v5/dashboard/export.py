"""Dashboard export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.dashboard.export import export_dashboard_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.dashboard.types import ExportDashboardApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportDashboardApiResponse)
async def export_dashboard(
    http_request: Request,
    response: Response,
) -> ExportDashboardApiResponse:
    """Export all dashboard data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()

    return await export_dashboard_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
    )
