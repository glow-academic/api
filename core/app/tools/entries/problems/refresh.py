"""Problems refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_problems(conn: asyncpg.Connection) -> None:
    """Refresh problems_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY problems_mv")
