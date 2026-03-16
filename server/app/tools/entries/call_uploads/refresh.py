"""Call uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_call_uploads(conn: asyncpg.Connection) -> None:
    """Refresh call_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY call_uploads_mv")
