"""Model export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.model.export import export_model_impl
from app.infra.model.types import ExportModelApiRequest, ExportModelApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportModelApiResponse)
async def export_models(
    body: ExportModelApiRequest,
    http_request: Request,
) -> ExportModelApiResponse:
    """Export all models as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_model_impl(
        pool,
        redis,
        profile_id=profile_id,
        model_id=body.model_id,
    )
