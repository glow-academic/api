"""home/refresh — reusable data-access layer."""

import time

import asyncpg

from app.utils.cache.invalidate_tags import invalidate_tags

MV_NAME = "home_mv"


async def refresh_home(conn: asyncpg.Connection) -> None:
    """Refresh home_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")


async def refresh_home_internal(
    conn: asyncpg.Connection,
) -> dict:
    """Refresh home_mv concurrently with cache invalidation."""
    start_time = time.time()
    await refresh_home(conn)
    duration_ms = int((time.time() - start_time) * 1000)
    await invalidate_tags(["entries", "home"], redis=get_redis_client())
    return {
        "success": True,
        "duration_ms": duration_ms,
        "message": f"Refreshed {MV_NAME} in {duration_ms}ms",
    }
