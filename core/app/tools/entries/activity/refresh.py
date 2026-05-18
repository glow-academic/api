"""Activity refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_activity(conn: asyncpg.Connection) -> None:
    """Refresh activity_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY activity_mv")
