"""Input: attempt.audio_upload

Socket equivalent of POST /attempt/audio/upload.
Accepts base64-encoded audio data since sockets can't do multipart.
"""

import base64
from typing import Any

from pydantic import BaseModel, Field

from app.infra.attempt.audio_upload import audio_upload_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import (
    get_internal_sio,
    get_pool,
    get_redis_client,
    get_upload_folder,
    sio,
)
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class AudioUploadSocketPayload(BaseModel):
    """Socket payload for attempt audio upload."""

    audio: str = Field(..., description="Base64-encoded audio data")
    filename: str = Field(..., description="Original filename (for extension + MIME detection)")
    content_type: str = Field("audio/webm", description="MIME type of the audio")
    length_seconds: int = Field(0, description="Duration of the audio in seconds")


@sio.on("attempt.audio_upload")  # type: ignore
async def attempt_audio_upload(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AudioUploadSocketPayload(**data)
    except Exception as e:
        await internal_sio.emit("attempt.audio_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    try:
        file_bytes = base64.b64decode(payload.audio)
    except Exception:
        await internal_sio.emit("attempt.audio_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Invalid base64 audio data",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="audio_upload",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: audio_upload_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_bytes=file_bytes,
            filename=payload.filename,
            content_type=payload.content_type,
            length_seconds=payload.length_seconds,
        ),
        arguments={
            "filename": payload.filename,
            "content_type": payload.content_type,
            "size": len(file_bytes),
            "length_seconds": payload.length_seconds,
        },
        upload_folder=get_upload_folder(),
    )
