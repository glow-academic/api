"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_completion_mv"


async def refresh_test_completion(conn: asyncpg.Connection) -> None:
    """Refresh test_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
