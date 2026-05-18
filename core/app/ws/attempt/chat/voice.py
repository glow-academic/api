"""Input: attempt.chat_voice"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.attempt.chat.voice import (
    attempt_chat_voice_internal_impl,
)


@sio.on("attempt.chat_voice")  # type: ignore
async def attempt_chat_voice(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return {"success": False}

    async def _runner() -> dict[str, Any]:
        result = await attempt_chat_voice_internal_impl({
            **data,
            "sid": sid,
            "profile_id": str(identity.profile_id),
            "session_id": str(identity.session_id),
        })
        return {"success": True, **result.model_dump()}

    pool = get_pool()
    redis = get_redis_client()

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat_voice",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=_runner,
        arguments={k: v for k, v in data.items() if k not in {"sid", "profile_id", "session_id"}},
    )
