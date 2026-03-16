"""Remove an active chat connection from Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def remove_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Remove a socket ID from an active chat connection set in Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return

    try:
        key = f"active_connection:{chat_id}"
        await redis_client.srem(key, socket_id)
        remaining = await redis_client.scard(key)
        if remaining == 0:
            await redis_client.delete(key)
    except Exception as e:
        logger.error(f"Redis error removing active connection for chat {chat_id}: {e}")
