"""Grant consumptions refresh — recompute the materialized view."""

import asyncpg


async def refresh_grant_consumptions(conn: asyncpg.Connection) -> None:
    """Refresh grant_consumptions_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY grant_consumptions_mv")
