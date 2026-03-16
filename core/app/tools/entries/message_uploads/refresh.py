"""Message uploads refresh — recompute the materialized view."""

import asyncpg


async def refresh_message_uploads(conn: asyncpg.Connection) -> None:
    """Refresh message_uploads_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY message_uploads_mv")
