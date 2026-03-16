"""Decrement guest connection count and return new total (floor at 0)."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def decrement_guest_count() -> int:
    """Decrement guest connection count and return new total (floor at 0)."""
    redis_client = get_redis_client()
    if not redis_client:
        return 0

    try:
        # Get current count and ensure it doesn't go below 0
        current = await redis_client.get("guest_connection_count")
        cur = int(current) if current else 0
        if cur <= 0:
            await redis_client.set("guest_connection_count", 0)
            return 0
        result = await redis_client.decr("guest_connection_count")
        return int(result) if result else 0
    except Exception as e:
        logger.error(f"Redis error decrementing guest count: {e}")
        return 0
