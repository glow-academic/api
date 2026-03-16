"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "audio_completion_mv"


async def refresh_audio_completion(conn: asyncpg.Connection) -> None:
    """Refresh audio_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
