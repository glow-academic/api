"""persona_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_persona_drafts(conn: asyncpg.Connection) -> None:
    """Refresh persona_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY persona_drafts_mv")
