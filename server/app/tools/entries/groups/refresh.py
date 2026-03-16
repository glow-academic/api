"""Groups refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_groups(conn: asyncpg.Connection) -> None:
    """Refresh groups_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
