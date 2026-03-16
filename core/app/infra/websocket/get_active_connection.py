"""Get the socket ID for an active chat connection from Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_active_connection(
    chat_id: str, *, redis_client: Any | None = None
) -> str | None:
    """Get the socket ID for an active chat connection from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return None

    try:
        connection_sids = await redis_client.smembers(f"active_connection:{chat_id}")
        if not connection_sids:
            return None
        return next(iter(connection_sids)).decode("utf-8")
    except Exception as e:
        logger.error(f"Redis error getting active connection for chat {chat_id}: {e}")
        return None
