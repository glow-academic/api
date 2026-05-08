"""Input: group.video_download

Socket equivalent of POST /group/video/download.
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
from app.infra.group.media_types import VideoDownloadGroupApiRequest
from app.infra.group.video_download import video_download_group_impl
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("system.group.video_download")  # type: ignore
async def group_video_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = VideoDownloadGroupApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("system.group_video_download.failed", {
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
        operation="group_video_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: video_download_group_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            video_id=payload.video_id,
        ),
        arguments={"video_id": str(payload.video_id)},
        upload_folder=get_upload_folder(),
    )
