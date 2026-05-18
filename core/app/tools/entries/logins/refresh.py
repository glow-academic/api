"""Logins refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_logins(conn: asyncpg.Connection) -> None:
    """Refresh logins_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY logins_mv")
