"""invocation_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_invocation_drafts(conn: asyncpg.Connection) -> None:
    """Refresh invocation_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY invocation_drafts_mv")
