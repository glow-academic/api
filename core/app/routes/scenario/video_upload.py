"""Scenario video upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.scenario.video_upload.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.scenario.group import group_scenario_impl
from app.infra.scenario.types import VideoUploadScenarioApiResponse
from app.infra.scenario.video_upload import video_upload_scenario_impl
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
}


@router.post("/video_upload", response_model=VideoUploadScenarioApiResponse)
async def upload_video(
    file: UploadFile,
    http_request: Request,
    response: Response,
    name: str | None = None,
    description: str | None = None,
) -> VideoUploadScenarioApiResponse:
    """Upload a video for later use in scenarios."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        # -- Validate file ------------------------------------------------------
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        content_type = file.content_type or get_content_type(file.filename)
        if content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video type: {content_type}",
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # -- Run with audit -----------------------------------------------------
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_scenario_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> VideoUploadScenarioApiResponse:
            return await video_upload_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=file.filename,
                content_type=content_type,
                name=name,
                description=description,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="video_upload",
            arguments={
                "filename": file.filename,
                "content_type": content_type,
                "size": len(file_bytes),
                "name": name,
                "description": description,
            },
            response_model=VideoUploadScenarioApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "uploads,resources,videos"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="video_upload_scenario",
            request=http_request,
        )
