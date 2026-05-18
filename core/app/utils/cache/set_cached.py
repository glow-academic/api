"""Store HTTP response in Redis with tag tracking."""

import json
from collections.abc import Iterable
from typing import Any

from redis.asyncio import Redis

from app.infra.cache_telemetry import record_write
from app.utils.logging.db_logger import get_logger

TAG_PREFIX = "http:tag:"

logger = get_logger(__name__)


async def set_cached(
    key: str,
    data: dict[str, Any],
    ttl: int,
    tags: Iterable[str],
    *,
    redis: Redis,
) -> None:
    """Store HTTP response in Redis with tag tracking.

    Per-write logging deferred to the request-scoped CacheTelemetry
    summary — see app/infra/cache_telemetry.py.
    """
    try:
        pipe = redis.pipeline()
        # Store response data
        pipe.setex(key, ttl, json.dumps(data))
        # Track which keys belong to each tag
        for tag in tags:
            pipe.sadd(f"{TAG_PREFIX}{tag}", key)
            pipe.expire(f"{TAG_PREFIX}{tag}", ttl)  # Expire tag set with cache
        await pipe.execute()
        record_write()
    except Exception as e:
        logger.error(f"Error writing cache: {e}", exc_info=True)
