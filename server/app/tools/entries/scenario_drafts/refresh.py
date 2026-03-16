"""scenario_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_scenario_drafts(conn: asyncpg.Connection) -> None:
    """Refresh scenario_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY scenario_drafts_mv")
