"""Tokens refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_tokens(conn: asyncpg.Connection) -> None:
    """Refresh tokens_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY tokens_mv")
