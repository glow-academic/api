"""Input: scenario.image_upload

Socket equivalent of POST /scenarios/image/upload.
Accepts base64-encoded image data since sockets can't do multipart.
"""

import base64
from typing import Any

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.image_upload import image_upload_scenario_impl

internal_sio = get_internal_sio()


class ImageUploadSocketPayload(BaseModel):
    """Socket payload for scenario image upload."""

    image: str = Field(..., description="Base64-encoded image data")
    filename: str = Field(..., description="Original filename (for extension + MIME detection)")
    content_type: str = Field("image/png", description="MIME type of the image")
    name: str | None = Field(None, description="Display name (defaults to filename)")
    description: str | None = Field(None, description="Image description")


@sio.on("scenario.image_upload")  # type: ignore
async def scenario_image_upload(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ImageUploadSocketPayload(**data)
    except Exception as e:
        await internal_sio.emit("scenario.image_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    try:
        file_bytes = base64.b64decode(payload.image)
    except Exception:
        await internal_sio.emit("scenario.image_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Invalid base64 image data",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="scenario",
        operation="image_upload",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: image_upload_scenario_impl(
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
