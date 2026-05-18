"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "video_completion_mv"


async def refresh_video_completion(conn: asyncpg.Connection) -> None:
    """Refresh video_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
