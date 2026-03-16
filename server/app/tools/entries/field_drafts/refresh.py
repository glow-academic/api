"""field_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_field_drafts(conn: asyncpg.Connection) -> None:
    """Refresh field_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY field_drafts_mv")
