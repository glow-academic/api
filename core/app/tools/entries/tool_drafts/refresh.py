"""tool_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_tool_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh tool_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY tool_drafts_mv")
