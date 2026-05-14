"""Input: attempt.chat_get

Event name uses the canonical ``<artifact>.<operation>`` convention
where ``operation`` is the single-token key from the operations
registry (``chat_get`` — underscore, not ``chat.get`` with a second
dot). The FE transport converts ``/attempt/chat_get`` to this exact
event name; the prior ``attempt.chat.get`` registration was a stale
regression that left every page load timing out on the chat hydrate.
"""

from typing import Any

from app.infra.attempt.chat.get import get_chat_impl
from app.infra.attempt.chat.types import GetChatRequest
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.chat_get")  # type: ignore
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
