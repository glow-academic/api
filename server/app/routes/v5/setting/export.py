"""Setting export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.setting.export import export_setting_impl
from app.infra.setting.types import ExportSettingApiRequest, ExportSettingApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportSettingApiResponse)
async def export_settings(
    body: ExportSettingApiRequest,
    http_request: Request,
) -> ExportSettingApiResponse:
    """Export all settings as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_setting_impl(
        pool,
        redis,
        profile_id=profile_id,
        setting_id=body.setting_id,
    )
