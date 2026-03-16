"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_feedback_mv"


async def refresh_attempt_feedback(conn: asyncpg.Connection) -> None:
    """Refresh attempt_feedback_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
