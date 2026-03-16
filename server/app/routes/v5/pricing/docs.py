"""Pricing docs endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.docs.types import ComposedDocsResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.globals import get_pool, get_redis_client
from app.infra.pricing.docs import docs_pricing_impl

router = APIRouter()


@router.post("/docs", response_model=ComposedDocsResponse)
async def get_pricing_docs_endpoint(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedDocsResponse:
    """Get composed documentation for the pricing analytics."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id

    return await docs_pricing_impl(
        pool,
        redis,
        profile_id=profile_id,
        entity_id=body.entity_id,
    )
