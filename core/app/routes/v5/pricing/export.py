"""Pricing export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.pricing.export import export_pricing_impl
from app.infra.pricing.types import ExportPricingApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportPricingApiResponse)
async def export_pricing(
    http_request: Request,
    response: Response,
) -> ExportPricingApiResponse:
    """Export all pricing data as a clean, denormalized ZIP."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id

    return await export_pricing_impl(
        pool,
        redis,
        profile_id=profile_id,
    )
