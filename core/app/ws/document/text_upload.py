"""Input: document.text_upload

Socket equivalent of POST /documents/text/upload.
Accepts base64-encoded text file data since sockets can't do multipart.
"""

import base64
from typing import Any

from pydantic import BaseModel, Field

from app.infra.document.text_upload import text_upload_document_impl
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


class TextUploadSocketPayload(BaseModel):
    """Socket payload for document text upload."""

    content: str = Field(..., description="Base64-encoded text file data")
    filename: str = Field(..., description="Original filename (for extension + MIME detection)")
    content_type: str = Field("text/plain", description="MIME type of the text file")


@sio.on("document.text_upload")  # type: ignore
async def document_text_upload(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = TextUploadSocketPayload(**data)
    except Exception as e:
        await internal_sio.emit("document.text_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    try:
        file_bytes = base64.b64decode(payload.content)
    except Exception:
        await internal_sio.emit("document.text_upload.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Invalid base64 text data",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="document",
        operation="text_upload",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: text_upload_document_impl(
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
