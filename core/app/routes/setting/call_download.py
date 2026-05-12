"""Setting call download endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.setting.call_download.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.infra.setting.call_download import call_download_setting_impl
from app.infra.setting.group import group_setting_impl
from app.infra.setting.types import (
    CallDownloadSettingApiRequest,
    CallDownloadSettingApiResult,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/call_download", response_model=None)
async def download_call(
    request: CallDownloadSettingApiRequest,
    http_request: Request,
    response: Response,
) -> FileResponse:
    """Download a call file by call resource ID."""
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

        group_id = None
        if session_id:
            group_result = await group_setting_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> CallDownloadSettingApiResult:
            return await call_download_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                call_id=request.call_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="setting",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="call_download",
            arguments={"call_id": str(request.call_id)},
            response_model=CallDownloadSettingApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        encoded = urllib.parse.quote(result.filename, safe="")
        content_disposition = (
            f"inline; filename=\"{encoded}\"; filename*=UTF-8\'\'{encoded}"
        )

        return FileResponse(
            path=result.file_path,
            media_type=result.content_type,
            headers={
                "Content-Disposition": content_disposition,
                "Cache-Control": "private, max-age=0, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="call_download_setting",
            request=http_request,
        )
