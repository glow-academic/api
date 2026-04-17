"""provider_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_provider_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh provider_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY provider_drafts_mv")
