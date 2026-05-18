"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_conversations_mv"


async def refresh_attempt_conversations(conn: asyncpg.Connection) -> None:
    """Refresh attempt_conversations_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
