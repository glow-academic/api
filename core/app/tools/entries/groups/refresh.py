"""Groups refresh — recompute the materialized view."""

import asyncpg  # type: ignore
from redis.asyncio import Redis


async def refresh_groups(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh groups_mv concurrently.

    Must refresh group_names_mv first since groups_mv joins on it.
    """
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
