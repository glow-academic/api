"""Tool export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.tool.export import export_tool_impl
from app.infra.tool.types import ExportToolApiRequest, ExportToolApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportToolApiResponse)
async def export_tools(
    body: ExportToolApiRequest,
    http_request: Request,
) -> ExportToolApiResponse:
    """Export all tools as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_tool_impl(
        pool,
        redis,
        profile_id=profile_id,
        tool_id=body.tool_id,
    )
