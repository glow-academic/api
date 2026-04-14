"""Attempt image download endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.image_download.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.image_download import image_download_attempt_impl
from app.infra.attempt.media_types import (
    ImageDownloadAttemptApiRequest,
    ImageDownloadAttemptApiResult,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/download", response_model=None)
async def download_image(
    request: ImageDownloadAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> FileResponse:
    """Download an image file by image entry ID."""
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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> ImageDownloadAttemptApiResult:
            return await image_download_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                image_id=request.image_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="image_download",
            arguments={"image_id": str(request.image_id)},
            response_model=ImageDownloadAttemptApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        encoded = urllib.parse.quote(result.filename, safe="")
        content_disposition = (
            f"inline; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
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
            operation="image_download_attempt",
            request=http_request,
        )
