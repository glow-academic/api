"""Get cached HTTP response from Redis."""

import json
from typing import Any

from redis.asyncio import Redis

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_cached(key: str, *, redis: Redis) -> dict[str, Any] | None:
    """Get cached HTTP response from Redis."""
    try:
        raw = await redis.get(key)
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            logger.info(f"Cache hit: key={key[:50]}...")
            return json.loads(raw)  # type: ignore
        else:
            logger.info(f"Cache miss: key={key[:50]}...")
    except Exception as e:
        logger.error(f"Error reading cache: {e}", exc_info=True)
    return None
