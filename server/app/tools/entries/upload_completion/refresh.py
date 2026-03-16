"""upload_completion/refresh internal — reusable data-access layer."""

import asyncpg

MV_NAME = "upload_completion_mv"


async def refresh_upload_completion(
    conn: asyncpg.Connection,
) -> None:
    """Refresh upload_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
