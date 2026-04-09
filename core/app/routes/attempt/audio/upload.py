"""Attempt audio upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.audio_upload.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from app.infra.attempt.audio_upload import audio_upload_attempt_impl
from app.infra.attempt.media_types import AudioUploadAttemptApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/aac",
    "audio/x-m4a",
    "audio/mp4",
    "audio/x-wav",
}


@router.post("/upload", response_model=AudioUploadAttemptApiResponse)
async def upload_audio(
    file: UploadFile,
    http_request: Request,
    response: Response,
    length_seconds: int = 0,
) -> AudioUploadAttemptApiResponse:
    """Upload an audio file for an attempt."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        # -- Validate file -----------------------------------------------------
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        content_type = file.content_type or get_content_type(file.filename)
        if content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio type: {content_type}",
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # -- Run with audit ----------------------------------------------------
        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> AudioUploadAttemptApiResponse:
            return await audio_upload_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=file.filename,
                content_type=content_type,
                length_seconds=length_seconds,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            operation="audio_upload",
            arguments={
                "filename": file.filename,
                "content_type": content_type,
                "size": len(file_bytes),
                "length_seconds": length_seconds,
            },
            response_model=AudioUploadAttemptApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "uploads,entries,audios"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="audio_upload_attempt",
            request=http_request,
        )
