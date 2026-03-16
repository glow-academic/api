"""cohort_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_cohort_drafts(conn: asyncpg.Connection) -> None:
    """Refresh cohort_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY cohort_drafts_mv")
