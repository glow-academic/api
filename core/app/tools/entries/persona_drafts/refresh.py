"""persona_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_persona_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh persona_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY persona_drafts_mv")
