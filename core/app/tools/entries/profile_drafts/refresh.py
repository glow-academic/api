"""profile_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_profile_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh profile_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY profile_drafts_mv")
