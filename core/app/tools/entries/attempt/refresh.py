"""attempt/refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_mv"


async def refresh_attempt(conn: asyncpg.Connection) -> None:
    """Refresh attempt_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
