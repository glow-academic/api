"""eval_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_eval_drafts(conn: asyncpg.Connection) -> None:
    """Refresh eval_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY eval_drafts_mv")
