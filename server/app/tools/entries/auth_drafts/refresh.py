"""auth_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_auth_drafts(conn: asyncpg.Connection) -> None:
    """Refresh auth_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY auth_drafts_mv")
