"""Image uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_image_uploads(conn: asyncpg.Connection) -> None:
    """Refresh image_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY image_uploads_mv")
