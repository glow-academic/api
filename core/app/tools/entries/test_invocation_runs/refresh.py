"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_invocation_runs_mv"


async def refresh_test_invocation_runs(conn: asyncpg.Connection) -> None:
    """Refresh test_invocation_runs_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
