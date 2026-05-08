"""Input: scenario.video_upload

Socket equivalent of POST /scenarios/video/upload.
Accepts base64-encoded video data since sockets can't do multipart.
"""

import base64
from typing import Any

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import (
    get_internal_sio,
    get_pool,
    get_redis_client,
    get_upload_folder,
    sio,
)
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.video_upload import video_upload_scenario_impl

internal_sio = get_internal_sio()


class VideoUploadSocketPayload(BaseModel):
    """Socket payload for scenario video upload."""

    video: str = Field(..., description="Base64-encoded video data")
    filename: str = Field(..., description="Original filename (for extension + MIME detection)")
    content_type: str = Field("video/mp4", description="MIME type of the video")
    name: str | None = Field(None, description="Display name (defaults to filename)")
    description: str | None = Field(None, description="Video description")


@sio.on("scenario.video_upload")  # type: ignore
async def scenario_video_upload(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = VideoUploadSocketPayload(**data)
    except Exception as e:
        await internal_sio.emit("scenario.video_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    try:
        file_bytes = base64.b64decode(payload.video)
    except Exception:
        await internal_sio.emit("scenario.video_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Invalid base64 video data",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="scenario",
        operation="video_upload",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: video_upload_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_bytes=file_bytes,
            filename=payload.filename,
            content_type=payload.content_type,
            name=payload.name,
            description=payload.description,
        ),
        arguments={
            "filename": payload.filename,
            "content_type": payload.content_type,
            "size": len(file_bytes),
            "name": payload.name,
            "description": payload.description,
        },
        upload_folder=get_upload_folder(),
    )
