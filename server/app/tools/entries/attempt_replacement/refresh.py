"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_replacement_mv"


async def refresh_attempt_replacement(conn: asyncpg.Connection) -> None:
    """Refresh attempt_replacement_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
