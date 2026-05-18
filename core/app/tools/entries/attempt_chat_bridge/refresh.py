"""Attempt chat bridge refresh — recompute the materialized view."""

import asyncpg


async def refresh_attempt_chat_bridge(conn: asyncpg.Connection) -> None:
    """Refresh attempt_chat_bridge_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY attempt_chat_bridge_mv")
