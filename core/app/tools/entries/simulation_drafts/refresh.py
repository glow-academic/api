"""simulation_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_simulation_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh simulation_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_drafts_mv")
