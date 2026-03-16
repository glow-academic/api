"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "text_completion_mv"


async def refresh_text_completion(conn: asyncpg.Connection) -> None:
    """Refresh text_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
