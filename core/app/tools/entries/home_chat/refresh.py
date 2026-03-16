"""home_chat/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "home_chat_mv"


async def refresh_home_chat(conn: asyncpg.Connection) -> None:
    """Refresh home_chat_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
