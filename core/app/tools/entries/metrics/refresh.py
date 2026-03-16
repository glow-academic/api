"""Metrics refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_metrics_internal(conn: asyncpg.Connection) -> None:
    """Refresh metrics_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY metrics_mv")
