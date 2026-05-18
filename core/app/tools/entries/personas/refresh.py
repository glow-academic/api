"""Personas refresh — recompute the materialized view."""

import asyncpg


async def refresh_personas(conn: asyncpg.Connection) -> None:
    """Refresh personas_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY personas_mv")
