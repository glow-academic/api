"""Attempt audio upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.audio_upload.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, UploadFile

from app.infra.attempt.audio_upload import audio_upload_attempt_impl
from app.infra.attempt.group import group_attempt_impl
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


@router.post("/audio_upload", response_model=AudioUploadAttemptApiResponse)
async def upload_audio(
    http_request: Request,
    response: Response,
    file: UploadFile | None = None,
    length_seconds: int = Form(0),
    upload_id: UUID | None = Query(None),
    name: str = Form(""),
    description: str = Form(""),
) -> AudioUploadAttemptApiResponse:
    """Upload audio or promote an existing raw upload.

    Three shapes:
      - **File only** → multipart ``file``: server writes bytes, creates
        ``uploads_entry`` + full audio chain on top.
      - **upload_id only** → ``?upload_id=<uuid>`` of an existing upload
        (e.g. raw bytes captured by the realtime adapter). Server reuses
        the upload and stacks resource + entry + junctions on top.
      - **upload_id + file** → client pre-reserved via ``/attempt/audio/new``
        and now fills the slot. Server writes bytes into that upload's
        file and then runs the full chain.

    Returns ``{audio_id, audios_id, upload_id}``. Client only needs
    ``audios_id``; ``upload_id`` is the primitive handed back.
    """
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        if upload_id is None and file is None:
            raise HTTPException(
                status_code=400,
                detail="Either a multipart 'file' or an 'upload_id' query param is required.",
            )

        file_bytes: bytes | None = None
        filename: str = ""
        content_type: str = "audio/pcm"

        if file is not None:
            if not file.filename:
                raise HTTPException(status_code=400, detail="Missing filename")

            filename = file.filename
            content_type = file.content_type or get_content_type(filename)
            # ``MediaRecorder`` returns codec-tagged content types like
            # ``audio/webm;codecs=opus`` — valid HTTP but a literal
            # string mismatch against the bare ``audio/webm`` in
            # ALLOWED_AUDIO_TYPES. Normalize by stripping parameters
            # before the membership check; persist the bare base type
            # so the upload row matches what other consumers (entry
            # search, MV) expect.
            base_content_type = content_type.split(";", 1)[0].strip().lower()
            if base_content_type not in ALLOWED_AUDIO_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported audio type: {content_type}",
                )
            content_type = base_content_type

            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Empty file")

        # -- Run with audit ----------------------------------------------------
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> AudioUploadAttemptApiResponse:
            return await audio_upload_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                upload_id=upload_id,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                length_seconds=length_seconds,
                name=name,
                description=description,
            )

        audit_arguments: dict = {
            "length_seconds": length_seconds,
        }
        if upload_id is not None:
            audit_arguments["upload_id"] = str(upload_id)
            audit_arguments["mode"] = "promote"
        else:
            audit_arguments.update(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(file_bytes or b""),
                    "mode": "file",
                }
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="audio_upload",
            arguments=audit_arguments,
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
