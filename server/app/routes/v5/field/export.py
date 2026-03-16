"""Field export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.field.export import export_field_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.field.types import ExportFieldApiRequest, ExportFieldApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportFieldApiResponse)
async def export_fields(
    body: ExportFieldApiRequest,
    http_request: Request,
) -> ExportFieldApiResponse:
    """Export all fields as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_field_impl(
        pool,
        redis,
        profile_id=profile_id,
        field_id=body.field_id,
    )
