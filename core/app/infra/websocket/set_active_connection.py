"""Add a socket ID to an active chat connection set in Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def set_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Add the socket ID to the active chat connections (1-hour TTL)."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    key = f"active_connection:{chat_id}"
    await redis_client.sadd(key, socket_id)
    await redis_client.expire(key, 3600)
