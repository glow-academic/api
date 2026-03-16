"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_archive_mv"


async def refresh_attempt_archive(conn: asyncpg.Connection) -> None:
    """Refresh attempt_archive_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
