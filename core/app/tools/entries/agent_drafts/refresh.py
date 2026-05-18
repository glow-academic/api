"""agent_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_agent_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh agent_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY agent_drafts_mv")
