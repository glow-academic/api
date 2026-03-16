"""Home export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.home_export import export_home_client
from app.infra.home.types import ExportHomeApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportHomeApiResponse)
async def export_home(
    http_request: Request,
    response: Response,
) -> ExportHomeApiResponse:
    """Export all home data as a clean, denormalized ZIP with certificate."""
    pool = get_pool()
    profile_id = http_request.state.profile_id

    return await export_home_client(
        pool,
        get_redis_client(),
        profile_id=profile_id,
    )
