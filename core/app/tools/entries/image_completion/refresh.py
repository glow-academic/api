"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "image_completion_mv"


async def refresh_image_completion(conn: asyncpg.Connection) -> None:
    """Refresh image_completion_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
