"""cohort_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_cohort_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh cohort_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY cohort_drafts_mv")
