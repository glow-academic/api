"""chat_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_chat_drafts(conn: asyncpg.Connection) -> None:
    """Refresh chat_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY chat_drafts_mv")
