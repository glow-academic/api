"""chat/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "chat_mv"


async def refresh_chat(conn: asyncpg.Connection) -> None:
    """Refresh chat_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
