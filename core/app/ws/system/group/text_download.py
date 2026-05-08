"""Input: group.text_download

Socket equivalent of POST /group/text/download.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import (
    get_internal_sio,
    get_pool,
    get_redis_client,
    get_upload_folder,
    sio,
)
from app.infra.group.media_types import TextDownloadGroupApiRequest
from app.infra.group.text_download import text_download_group_impl
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("system.group.text_download")  # type: ignore
async def group_text_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = TextDownloadGroupApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("system.group_text_download.failed", {
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
        artifact="system",
        operation="group_text_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: text_download_group_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            text_id=payload.text_id,
        ),
        arguments={"text_id": str(payload.text_id)},
        upload_folder=get_upload_folder(),
    )
