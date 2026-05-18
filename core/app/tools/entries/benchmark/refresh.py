"""Benchmark refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "benchmark_mv"


async def refresh_benchmark(conn: asyncpg.Connection) -> None:
    """Refresh benchmark_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
