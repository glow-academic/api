"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_archive_mv"


async def refresh_test_archive(conn: asyncpg.Connection) -> None:
    """Refresh test_archive_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
