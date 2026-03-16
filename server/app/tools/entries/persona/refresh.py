"""Persona refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_persona_internal(conn: asyncpg.Connection) -> None:
    """Refresh personas_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY personas_mv")
