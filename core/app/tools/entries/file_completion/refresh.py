"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "file_completion_mv"


async def refresh_file_completion(conn: asyncpg.Connection) -> None:
    """Refresh file_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
