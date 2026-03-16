"""document_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_document_drafts(conn: asyncpg.Connection) -> None:
    """Refresh document_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY document_drafts_mv")
