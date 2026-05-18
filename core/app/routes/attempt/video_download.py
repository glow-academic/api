"""Attempt video download endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.video_download.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.media_types import (
    VideoDownloadAttemptApiRequest,
    VideoDownloadAttemptApiResult,
)
from app.infra.attempt.video_download import video_download_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.storage.range_response import create_range_response

router = APIRouter()


@router.post("/video_download", response_model=None)
async def download_video(
    request: VideoDownloadAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> Response:
    """Download a video file by video entry ID with range support for seeking."""
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

        async def _runner() -> VideoDownloadAttemptApiResult:
            return await video_download_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                video_id=request.video_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="video_download",
            arguments={"video_id": str(request.video_id)},
            response_model=VideoDownloadAttemptApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        encoded = urllib.parse.quote(result.filename, safe="")
        content_disposition = (
            f"inline; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )

        return create_range_response(
            file_path=result.file_path,
            content_type=result.content_type,
            content_disposition=content_disposition,
            range_header=http_request.headers.get("range"),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="video_download_attempt",
            request=http_request,
        )
