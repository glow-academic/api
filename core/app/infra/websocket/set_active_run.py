"""Set the active run ID for a chat in Redis."""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def set_active_run(
    chat_id: str, run_id: str, *, redis_client: Any | None = None
) -> None:
    """Set the active run ID for a chat in Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    if not redis_client:
        return

    try:
        # Set with expiration (2 hours) to prevent stale data
        await redis_client.setex(f"active_run:{chat_id}", 7200, run_id)
    except Exception as e:
        logger.error(f"Redis error setting active run for chat {chat_id}: {e}")
