"""Setting create endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.setting.create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.setting.create import create_setting_impl
from app.infra.setting.types import (
    CreateSettingApiRequest,
    CreateSettingApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/create", response_model=CreateSettingApiResponse)
async def create_setting(
    request: CreateSettingApiRequest,
    http_request: Request,
    response: Response,
) -> CreateSettingApiResponse:
    """Create settings using composable infra architecture."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateSettingApiResponse:
            return await create_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.settings,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="setting",
            profile_id=profile_id,
            session_id=session_id,
            operation="create",
            arguments={
                "settings": [item.model_dump(mode="json") for item in request.settings]
            },
            response_model=CreateSettingApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "settings"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_setting",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
