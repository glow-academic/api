"""Practice export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.practice_export import export_practice_client
from app.infra.practice.types import ExportPracticeApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportPracticeApiResponse)
async def export_practice(
    http_request: Request,
    response: Response,
) -> ExportPracticeApiResponse:
    """Export all practice data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_practice_client(
        pool,
        redis,
        profile_id=profile_id,
    )
