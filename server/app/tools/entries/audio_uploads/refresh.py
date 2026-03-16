"""Audio uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_audio_uploads(conn: asyncpg.Connection) -> None:
    """Refresh audio_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY audio_uploads_mv")
