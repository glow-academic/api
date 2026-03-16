"""Get the active run ID for a chat from Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_active_run(
    chat_id: str, *, redis_client: Any | None = None
) -> str | None:
    """Get the active run ID for a chat from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return None

    try:
        run_id = await redis_client.get(f"active_run:{chat_id}")
        return run_id.decode("utf-8") if run_id else None
    except Exception as e:
        logger.error(f"Redis error getting active run for chat {chat_id}: {e}")
        return None
