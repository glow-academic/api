"""agent_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_agent_drafts(conn: asyncpg.Connection) -> None:
    """Refresh agent_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY agent_drafts_mv")
