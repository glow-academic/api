"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_strength_mv"


async def refresh_attempt_strength(conn: asyncpg.Connection) -> None:
    """Refresh attempt_strength_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
