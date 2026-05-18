"""practice_chat/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "practice_chat_mv"


async def refresh_practice_chat(conn: asyncpg.Connection) -> None:
    """Refresh practice_chat_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
