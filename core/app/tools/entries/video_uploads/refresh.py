"""Video uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_video_uploads(conn: asyncpg.Connection) -> None:
    """Refresh video_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY video_uploads_mv")
