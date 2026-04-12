"""Group names refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_group_names(conn: asyncpg.Connection) -> None:
    """Refresh group_names_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
