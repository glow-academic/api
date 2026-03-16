"""rubric_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_rubric_drafts(conn: asyncpg.Connection) -> None:
    """Refresh rubric_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY rubric_drafts_mv")
