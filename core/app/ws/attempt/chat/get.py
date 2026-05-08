"""Input: attempt.chat.get"""

from typing import Any

from app.infra.attempt.chat.get import get_chat_impl
from app.infra.attempt.chat.types import GetChatRequest
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


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
