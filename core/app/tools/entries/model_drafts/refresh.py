"""model_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_model_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh model_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY model_drafts_mv")
