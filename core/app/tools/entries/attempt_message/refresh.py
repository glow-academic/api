"""attempt_message/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_message_mv"


async def refresh_attempt_message(conn: asyncpg.Connection) -> None:
    """Refresh attempt_message_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
