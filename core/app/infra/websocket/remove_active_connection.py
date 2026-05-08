"""Remove a socket from an active chat connection set in Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def remove_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Remove socket from the chat connection set; drop the key when empty."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    key = f"active_connection:{chat_id}"
    await redis_client.srem(key, socket_id)
    if await redis_client.scard(key) == 0:
        await redis_client.delete(key)
