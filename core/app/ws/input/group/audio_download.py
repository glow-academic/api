"""Input: group.audio_download

Socket equivalent of POST /group/audio/download.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, get_upload_folder, sio
from app.infra.group.audio_download import audio_download_group_impl
from app.infra.group.media_types import AudioDownloadGroupApiRequest
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("group.audio_download")  # type: ignore
async def group_audio_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AudioDownloadGroupApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("group.audio_download.failed", {
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
        operation="audio_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: audio_download_group_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            audio_id=payload.audio_id,
        ),
        arguments={"audio_id": str(payload.audio_id)},
        upload_folder=get_upload_folder(),
    )
