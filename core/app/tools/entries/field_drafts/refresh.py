"""field_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_field_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh field_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY field_drafts_mv")
