"""simulation_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_simulation_drafts(conn: asyncpg.Connection) -> None:
    """Refresh simulation_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_drafts_mv")
