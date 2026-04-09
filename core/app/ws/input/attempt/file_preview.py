"""Input: attempt.file_preview

Socket equivalent of POST /attempt/file/preview.
Returns base64-encoded PNG preview data since sockets can't stream files.
"""

from typing import Any

from app.infra.attempt.file_preview import file_preview_attempt_impl
from app.infra.attempt.media_types import FilePreviewAttemptApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("attempt.file_preview")  # type: ignore
async def attempt_file_preview(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = FilePreviewAttemptApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.file_preview.failed", {
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
        artifact="attempt",
        operation="file_preview",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: file_preview_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            file_id=payload.file_id,
        ),
        arguments={"file_id": str(payload.file_id)},
        upload_folder=get_upload_folder(),
    )
