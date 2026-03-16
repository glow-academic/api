"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_mutes_mv"


async def refresh_attempt_mutes(conn: asyncpg.Connection) -> None:
    """Refresh attempt_mutes_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
