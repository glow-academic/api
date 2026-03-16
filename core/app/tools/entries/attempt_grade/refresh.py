"""Entry refresh — reusable data-access layer."""

import asyncpg  # type: ignore

MV_NAME = "attempt_grade_mv"


async def refresh_attempt_grade(conn: asyncpg.Connection) -> None:
    """Refresh attempt_grade_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
