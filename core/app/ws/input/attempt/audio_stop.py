"""Input: attempt.audio_stop"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.attempt.audio_stop import (
    attempt_audio_stop_internal_impl,
)


@sio.on("attempt.chat.silence")  # type: ignore
async def attempt_audio_stop(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    chat_id = data.get("chat_id")
    if not chat_id:
        return

    async def _runner() -> dict[str, Any]:
        await attempt_audio_stop_internal_impl({"chat_id": chat_id, "sid": sid})
        return {"chat_id": chat_id, "success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat.silence",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={"chat_id": chat_id},
    )
