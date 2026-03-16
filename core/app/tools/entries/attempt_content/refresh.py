"""Entry refresh — reusable data-access layer."""

import asyncpg  # type: ignore

MV_NAME = "attempt_content_mv"


async def refresh_attempt_content(conn: asyncpg.Connection) -> None:
    """Refresh attempt_content_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
