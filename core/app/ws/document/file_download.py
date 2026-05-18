"""Input: document.file_download

Socket equivalent of POST /documents/file/download.
Returns base64-encoded file data since sockets can't stream files.
"""

from typing import Any

from app.infra.document.file_download import file_download_document_impl
from app.infra.document.types import FileDownloadDocumentApiRequest
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


@sio.on("document.file_download")  # type: ignore
async def document_file_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = FileDownloadDocumentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("document.file_download.failed", {
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
        operation="file_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: file_download_document_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_id=payload.file_id,
        ),
        arguments={"file_id": str(payload.file_id)},
        upload_folder=get_upload_folder(),
    )
