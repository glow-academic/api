"""Input: attempt.chat_silence"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.attempt.chat.silence import (
    attempt_chat_silence_internal_impl,
)


@sio.on("attempt.chat_silence")  # type: ignore
async def attempt_chat_silence(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    chat_id = data.get("chat_id")
    if not chat_id:
        return

    async def _runner() -> dict[str, Any]:
        # Pass the resolved caller profile so the impl's owner guard (R3) can
        # deny silencing another user's live voice session. The WS path skips
        # the audit wrapper (no session_id), but the profile still threads
        # straight into ``_perform_silence``'s ownership check.
        await attempt_chat_silence_internal_impl(
            {
                "chat_id": chat_id,
                "sid": sid,
                "profile_id": str(identity.profile_id) if identity.profile_id else None,
            }
        )
        return {"chat_id": chat_id, "success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat_silence",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=_runner,
        arguments={"chat_id": chat_id},
    )
