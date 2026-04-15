"""Input: group.image_download

Socket equivalent of POST /group/image/download.
Returns base64-encoded image data since sockets can't stream files.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, get_upload_folder, sio
from app.infra.group.image_download import image_download_group_impl
from app.infra.group.media_types import ImageDownloadGroupApiRequest
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("system.group.image_download")  # type: ignore
async def group_image_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ImageDownloadGroupApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("group.image_download.failed", {
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
        artifact="group",
        operation="image_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: image_download_group_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            image_id=payload.image_id,
        ),
        arguments={"image_id": str(payload.image_id)},
        upload_folder=get_upload_folder(),
    )
