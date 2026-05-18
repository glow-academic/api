"""Input: attempt.audio_download

Socket equivalent of POST /attempt/audio/download.
Returns base64-encoded audio data since sockets can't stream files.
"""

from typing import Any

from app.infra.attempt.audio_download import audio_download_attempt_impl
from app.infra.attempt.media_types import AudioDownloadAttemptApiRequest
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


@sio.on("attempt.audio_download")  # type: ignore
async def attempt_audio_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AudioDownloadAttemptApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.audio_download.failed", {
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
        operation="audio_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: audio_download_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            audio_id=payload.audio_id,
        ),
        arguments={"audio_id": str(payload.audio_id)},
        upload_folder=get_upload_folder(),
    )
