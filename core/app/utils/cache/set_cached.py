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
            tag_key = f"{TAG_PREFIX}{tag}"
            pipe.sadd(tag_key, key)
            # The tag set must outlive its longest-lived member so that
            # invalidate_tags (which SMEMBERS the set) can still reach every
            # live key.  A plain EXPIRE would let a short-TTL write shrink a
            # set that already holds longer-lived keys, orphaning them.  Set
            # the TTL to the MAX of current and new instead, never shrinking:
            #   NX -> establish the initial TTL on a fresh set (GT alone never
            #         sets a TTL because a key with none is treated as
            #         infinite, which would orphan the set forever);
            #   GT -> only extend, never reduce, an existing TTL.
            # Requires Redis 7+ (NX/GT flags) — prod + tests run redis:7-alpine.
            pipe.expire(tag_key, ttl, nx=True)
            pipe.expire(tag_key, ttl, gt=True)
        await pipe.execute()
        record_write()
    except Exception as e:
        logger.error(f"Error writing cache: {e}", exc_info=True)
