"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_invocation_traces_mv"


async def refresh_test_invocation_traces(conn: asyncpg.Connection) -> None:
    """Refresh test_invocation_traces_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
