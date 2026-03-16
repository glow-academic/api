"""Profile export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.profile.export import export_profile_impl
from app.infra.profile.types import ExportProfileApiRequest, ExportProfileApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportProfileApiResponse)
async def export_profiles(
    body: ExportProfileApiRequest,
    http_request: Request,
) -> ExportProfileApiResponse:
    """Export all profiles as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_profile_impl(
        pool,
        redis,
        profile_id=profile_id,
        profile_export_id=body.profile_export_id,
    )
