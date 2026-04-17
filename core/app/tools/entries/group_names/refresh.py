"""Group names refresh — recompute the materialized view."""

import asyncpg  # type: ignore
from redis.asyncio import Redis


async def refresh_group_names(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh group_names_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
