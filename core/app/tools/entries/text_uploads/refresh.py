"""Text uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_text_uploads(conn: asyncpg.Connection) -> None:
    """Refresh text_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY text_uploads_mv")
