"""Entry refresh — reusable data-access layer."""

import asyncpg  # type: ignore

MV_NAME = "test_grade_mv"


async def refresh_test_grade(conn: asyncpg.Connection) -> None:
    """Refresh test_grade_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
