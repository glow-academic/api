"""Input: attempt.audio_start"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.attempt.audio_start import (
    attempt_audio_start_internal_impl,
)


@sio.on("attempt.chat.voice")  # type: ignore
async def attempt_audio_start(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    async def _runner() -> dict[str, Any]:
        await attempt_audio_start_internal_impl({
            **data,
            "sid": sid,
            "profile_id": str(identity.profile_id),
            "session_id": str(identity.session_id),
        })
        return {"success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat.voice",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={k: v for k, v in data.items() if k not in {"sid", "profile_id", "session_id"}},
    )
