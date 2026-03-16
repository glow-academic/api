"""Entry refresh — reusable data-access layer."""

import asyncpg  # type: ignore

MV_NAME = "attempt_hint_mv"


async def refresh_attempt_hint(conn: asyncpg.Connection) -> None:
    """Refresh attempt_hint_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
