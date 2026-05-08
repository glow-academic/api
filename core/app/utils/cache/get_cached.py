"""Get cached HTTP response from Redis."""

import json
from typing import Any

from redis.asyncio import Redis

from app.infra.cache_telemetry import record_hit, record_miss
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_cached(key: str, *, redis: Redis) -> dict[str, Any] | None:
    """Get cached HTTP response from Redis.

    Per-event hit/miss is NOT logged here — it would flood the server
    log with one line per internal sub-fetch. Instead, counts are
    pushed onto the request-scoped ``CacheTelemetry`` accumulator and
    summarized in a single line by the request middleware. See
    ``app/infra/cache_telemetry.py`` for the mechanism.
    """
    try:
        raw = await redis.get(key)
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            record_hit()
            return json.loads(raw)  # type: ignore
        else:
            record_miss()
    except Exception as e:
        logger.error(f"Error reading cache: {e}", exc_info=True)
    return None
