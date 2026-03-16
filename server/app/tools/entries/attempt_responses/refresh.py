"""Entry refresh — reusable data-access layer."""

import asyncpg  # type: ignore

MV_NAME = "attempt_responses_mv"


async def refresh_attempt_responses(conn: asyncpg.Connection) -> None:
    """Refresh attempt_responses_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
