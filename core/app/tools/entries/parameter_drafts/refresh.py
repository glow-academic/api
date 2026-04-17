"""parameter_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_parameter_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh parameter_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY parameter_drafts_mv")
