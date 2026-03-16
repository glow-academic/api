"""Run pricing refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_run_pricing_internal(conn: asyncpg.Connection) -> None:
    """Refresh run_pricing_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv")
