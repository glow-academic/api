"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_highlight_mv"


async def refresh_attempt_highlight(conn: asyncpg.Connection) -> None:
    """Refresh attempt_highlight_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
