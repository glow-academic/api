"""Leaderboard export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.leaderboard.export import export_leaderboard_impl
from app.infra.leaderboard.types import ExportLeaderboardApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportLeaderboardApiResponse)
async def export_leaderboard(
    http_request: Request,
    response: Response,
) -> ExportLeaderboardApiResponse:
    """Export all leaderboard data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_leaderboard_impl(
        pool,
        redis,
        profile_id=profile_id,
    )
