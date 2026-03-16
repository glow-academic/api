"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_improvement_mv"


async def refresh_attempt_improvement(conn: asyncpg.Connection) -> None:
    """Refresh attempt_improvement_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
