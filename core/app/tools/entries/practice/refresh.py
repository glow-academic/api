"""practice/refresh — reusable data-access layer."""

import time

import asyncpg

from app.utils.cache.invalidate_tags import invalidate_tags

MV_NAME = "practice_mv"


async def refresh_practice(conn: asyncpg.Connection) -> None:
    """Refresh practice_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")


async def refresh_practice_internal(
    conn: asyncpg.Connection,
) -> dict:
    """Refresh practice_mv concurrently with cache invalidation."""
    start_time = time.time()
    await refresh_practice(conn)
    duration_ms = int((time.time() - start_time) * 1000)
    await invalidate_tags(["entries", "practice"], redis=get_redis_client())
    return {
        "success": True,
        "duration_ms": duration_ms,
        "message": f"Refreshed {MV_NAME} in {duration_ms}ms",
    }
