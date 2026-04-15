"""Health export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.health.export import export_health_impl
from app.infra.health.types import ExportHealthApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportHealthApiResponse)
async def export_health(
    http_request: Request,
    response: Response,
) -> ExportHealthApiResponse:
    """Export all health data as a clean, denormalized ZIP."""
    pool = get_pool()
    profile_id = http_request.state.profile_id

    return await export_health_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
    )
