"""attempt_chat/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_chat_mv"


async def refresh_attempt_chat(conn: asyncpg.Connection) -> None:
    """Refresh attempt_chat_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
