"""health/get — reusable data-access layer."""

from datetime import datetime

import asyncpg  # type: ignore

from app.tools.entries.health.types import GetHealthResponse

MV_NAME = "health_mv"


async def get_health(
    conn: asyncpg.Connection,
    ids: list[datetime],
) -> list[GetHealthResponse]:
    """Get health entries by date_hour IDs from health_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT date_hour, service, check_count, ok_count, fail_count,
               uptime_percent, avg_latency_ms, min_latency_ms, max_latency_ms,
               latest_ok, latest_error
        FROM {MV_NAME}
        WHERE date_hour = ANY($1)
        """,
        ids,
    )

    return [GetHealthResponse(**dict(r)) for r in rows]
