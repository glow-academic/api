"""metrics/get — reusable data-access layer."""

from datetime import datetime

import asyncpg  # type: ignore

from app.tools.entries.metrics.types import GetMetricsSearchResponse

MV_NAME = "metrics_mv"


async def get_metrics(
    conn: asyncpg.Connection,
    ids: list[datetime],
) -> list[GetMetricsSearchResponse]:
    """Get metrics entries by date_hour IDs from metrics_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT date_hour, sample_count,
               avg_cpu_percent, min_cpu_percent, max_cpu_percent,
               avg_latency_ms, min_latency_ms, max_latency_ms,
               avg_memory_bytes, min_memory_bytes, max_memory_bytes,
               max_requests_total, max_errors_total
        FROM {MV_NAME}
        WHERE date_hour = ANY($1)
        """,
        ids,
    )

    return [GetMetricsSearchResponse(**dict(r)) for r in rows]
