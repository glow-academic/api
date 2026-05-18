"""document_drafts refresh — recompute the materialized view."""

import asyncpg
from redis.asyncio import Redis


async def refresh_document_drafts(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh document_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY document_drafts_mv")
