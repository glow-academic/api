"""Sessions refresh — recompute the materialized view."""

import asyncpg


async def refresh_sessions(conn: asyncpg.Connection) -> None:
    """Refresh sessions_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY sessions_mv")
