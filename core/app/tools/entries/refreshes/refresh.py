"""Refresh MV refresh — reusable data-access layer."""

import time

import asyncpg

from app.infra.globals import get_redis_client
from app.utils.cache.invalidate_tags import invalidate_tags

MV_NAME = "refresh_mv"


async def refresh_refreshes_internal(
    conn: asyncpg.Connection,
) -> dict:
    """Refresh refresh_mv concurrently."""
    start_time = time.time()
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
    duration_ms = int((time.time() - start_time) * 1000)
    await invalidate_tags(["entries", "refreshes"], redis=get_redis_client())
    return {
        "success": True,
        "duration_ms": duration_ms,
        "message": f"Refreshed {MV_NAME} in {duration_ms}ms",
    }
