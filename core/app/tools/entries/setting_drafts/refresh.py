"""setting_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_setting_drafts(conn: asyncpg.Connection) -> None:
    """Refresh setting_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY setting_drafts_mv")
