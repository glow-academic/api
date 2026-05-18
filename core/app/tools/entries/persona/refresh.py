"""Persona refresh — recompute the materialized view."""

import asyncpg  # type: ignore
from redis.asyncio import Redis


async def refresh_persona_internal(conn: asyncpg.Connection, redis: Redis | None = None) -> None:
    """Refresh personas_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY personas_mv")
