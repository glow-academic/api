"""Soft calls refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_soft_calls(conn: asyncpg.Connection) -> None:
    """Refresh soft_calls_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY soft_calls_mv")
