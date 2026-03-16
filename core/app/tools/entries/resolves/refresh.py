"""Resolves refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_resolves(conn: asyncpg.Connection) -> None:
    """Refresh resolves_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY resolves_mv")
