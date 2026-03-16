"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_feedback_mv"


async def refresh_test_feedback(conn: asyncpg.Connection) -> None:
    """Refresh test_feedback_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
