"""Logouts refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_logouts(conn: asyncpg.Connection) -> None:
    """Refresh logouts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY logouts_mv")
