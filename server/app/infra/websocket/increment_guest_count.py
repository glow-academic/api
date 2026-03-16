"""Increment guest connection count and return new total."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def increment_guest_count() -> int:
    """Increment guest connection count and return new total."""
    redis_client = get_redis_client()
    if not redis_client:
        return 0

    try:
        result = await redis_client.incr("guest_connection_count")
        return int(result) if result else 0
    except Exception as e:
        logger.error(f"Redis error incrementing guest count: {e}")
        return 0
