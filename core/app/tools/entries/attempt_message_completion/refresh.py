"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_message_completion_mv"


async def refresh_attempt_message_completion(conn: asyncpg.Connection) -> None:
    """Refresh attempt_message_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
