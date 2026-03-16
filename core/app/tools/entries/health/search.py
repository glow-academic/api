"""Health search — filtered/paginated query against health_mv."""

from datetime import datetime

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.health.types import GetHealthResponse

MV_NAME = "health_mv"


async def search_health(
    conn: asyncpg.Connection,
    service: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetHealthResponse]:
    """Search health entries from health_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    rows = await conn.fetch(
        f"""
        SELECT date_hour, service, check_count, ok_count, fail_count,
               uptime_percent, avg_latency_ms, min_latency_ms, max_latency_ms,
               latest_ok, latest_error
        FROM {source}
        WHERE ($1::text IS NULL OR service = $1)
          AND ($2::timestamptz IS NULL OR date_hour >= $2)
          AND ($3::timestamptz IS NULL OR date_hour <= $3)
        ORDER BY date_hour {order}
        LIMIT $4 OFFSET $5
        """,
        service,
        date_from,
        date_to,
        limit,
        offset,
    )

    return [GetHealthResponse(**dict(r)) for r in rows]
