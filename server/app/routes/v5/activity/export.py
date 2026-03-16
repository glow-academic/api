"""Activity export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.activity.export import export_activity_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.activity.types import ExportActivityApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportActivityApiResponse)
async def export_activity(
    http_request: Request,
    response: Response,
) -> ExportActivityApiResponse:
    """Export all activity data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_activity_impl(
        pool,
        redis,
        profile_id=profile_id,
    )
