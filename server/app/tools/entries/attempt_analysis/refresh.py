"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_analysis_mv"


async def refresh_attempt_analysis(conn: asyncpg.Connection) -> None:
    """Refresh attempt_analysis_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
