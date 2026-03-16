"""Provider export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.provider.export import export_provider_impl
from app.infra.provider.types import ExportProviderApiRequest, ExportProviderApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportProviderApiResponse)
async def export_providers(
    body: ExportProviderApiRequest,
    http_request: Request,
) -> ExportProviderApiResponse:
    """Export all providers as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_provider_impl(
        pool,
        redis,
        profile_id=profile_id,
        provider_id=body.provider_id,
    )
