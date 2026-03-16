"""Attempt home refresh — recompute the materialized view."""

import asyncpg


async def refresh_attempt_home(conn: asyncpg.Connection) -> None:
    """Refresh attempt_home_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY attempt_home_mv")
