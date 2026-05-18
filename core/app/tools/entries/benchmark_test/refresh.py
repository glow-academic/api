"""Benchmark test refresh — recompute the materialized view."""

import asyncpg


async def refresh_benchmark_test(conn: asyncpg.Connection) -> None:
    """Refresh benchmark_test_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY benchmark_test_mv")
