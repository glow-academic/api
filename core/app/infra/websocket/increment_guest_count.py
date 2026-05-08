"""Increment guest connection count and return new total."""

from app.infra.globals import get_redis_client


async def increment_guest_count() -> int:
    """Increment guest connection count and return new total."""
    redis_client = get_redis_client()
    result = await redis_client.incr("guest_connection_count")
    return int(result) if result else 0
