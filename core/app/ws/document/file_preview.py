"""Input: document.file_preview

Socket equivalent of POST /documents/file/preview.
Returns base64-encoded PNG preview since sockets can't stream binary.
"""

from typing import Any

from app.infra.document.file_preview import file_preview_document_impl
from app.infra.document.types import FilePreviewDocumentApiRequest
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


@sio.on("document.file_preview")  # type: ignore
async def document_file_preview(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = FilePreviewDocumentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("document.file_preview.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="document",
        operation="file_preview",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: file_preview_document_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_id=payload.file_id,
        ),
        arguments={"file_id": str(payload.file_id)},
        upload_folder=get_upload_folder(),
    )
