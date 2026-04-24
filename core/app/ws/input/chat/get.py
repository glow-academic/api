"""Input: chat.get"""

from typing import Any

from app.infra.chat.get import get_chat_impl
from app.infra.chat.types import GetChatRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("attempt.chat.get")  # type: ignore
async def attempt_chat_get(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    """Ack-based handler — returns chat data directly via socket.io acknowledgement."""
    identity = await resolve_socket_identity(sid)
    if not identity:
        return {"error": "Not authenticated"}

    try:
        payload = GetChatRequest(**data)
        pool = get_pool()
        redis = get_redis_client()
        result = await get_chat_impl(
            pool, redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        )
        return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    except Exception as e:
        return {"error": str(e)}


@sio.on("chat.get")  # type: ignore
async def chat_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetChatRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.chat_get.failed", {
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
        operation="chat_get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_chat_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
