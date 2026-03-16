"""parameter_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_parameter_drafts(conn: asyncpg.Connection) -> None:
    """Refresh parameter_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY parameter_drafts_mv")
