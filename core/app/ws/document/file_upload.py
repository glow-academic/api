"""Input: document.file_upload

Socket equivalent of POST /documents/file/upload.
Accepts base64-encoded file data since sockets can't do multipart.
"""

import base64
from typing import Any

from pydantic import BaseModel, Field

from app.infra.document.file_upload import file_upload_document_impl
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


class FileUploadSocketPayload(BaseModel):
    """Socket payload for document file upload."""

    file: str = Field(..., description="Base64-encoded file data")
    filename: str = Field(..., description="Original filename (for extension + MIME detection)")
    content_type: str = Field("application/octet-stream", description="MIME type of the file")


@sio.on("document.file_upload")  # type: ignore
async def document_file_upload(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = FileUploadSocketPayload(**data)
    except Exception as e:
        await internal_sio.emit("document.file_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    try:
        file_bytes = base64.b64decode(payload.file)
    except Exception:
        await internal_sio.emit("document.file_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Invalid base64 file data",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="document",
        operation="file_upload",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: file_upload_document_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_bytes=file_bytes,
            filename=payload.filename,
            content_type=payload.content_type,
        ),
        arguments={
            "filename": payload.filename,
            "content_type": payload.content_type,
            "size": len(file_bytes),
        },
        upload_folder=get_upload_folder(),
    )
