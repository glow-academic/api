"""Auth export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.auth.export import export_auth_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.auth.types import ExportAuthApiRequest, ExportAuthApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportAuthApiResponse)
async def export_auths(
    body: ExportAuthApiRequest,
    http_request: Request,
) -> ExportAuthApiResponse:
    """Export all auths as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_auth_impl(
        pool,
        redis,
        profile_id=profile_id,
        auth_id=body.auth_id,
    )
