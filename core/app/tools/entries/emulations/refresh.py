"""Emulations refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_emulations(conn: asyncpg.Connection) -> None:
    """Refresh emulations_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY emulations_mv")
