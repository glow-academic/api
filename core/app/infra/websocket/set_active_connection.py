"""Set the socket ID for an active chat connection in Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def set_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Add the socket ID to the active chat connections in Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return

    try:
        # Add to set and refresh expiration (1 hour) to prevent stale data
        await redis_client.sadd(f"active_connection:{chat_id}", socket_id)
        await redis_client.expire(f"active_connection:{chat_id}", 3600)
    except Exception as e:
        logger.error(f"Redis error setting active connection for chat {chat_id}: {e}")
