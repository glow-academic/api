"""File uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_file_uploads(conn: asyncpg.Connection) -> None:
    """Refresh file_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY file_uploads_mv")
