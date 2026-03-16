"""Remove an active run from Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def remove_active_run(chat_id: str, *, redis_client: Any | None = None) -> None:
    """Remove an active run from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return

    try:
        await redis_client.delete(f"active_run:{chat_id}")
    except Exception as e:
        logger.error(f"Redis error removing active run for chat {chat_id}: {e}")
