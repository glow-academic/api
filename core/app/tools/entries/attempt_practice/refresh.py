"""Attempt practice refresh — recompute the materialized view."""

import asyncpg


async def refresh_attempt_practice(conn: asyncpg.Connection) -> None:
    """Refresh attempt_practice_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY attempt_practice_mv")
