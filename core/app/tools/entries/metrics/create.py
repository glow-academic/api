"""metrics/create internal — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.metrics.types import CreateMetricsEntryResponse
from app.tools.entries.sessions.create import create_session


async def create_metrics_entry_internal(
    conn: asyncpg.Connection,
    ts: datetime,
    requests_total: int,
    errors_total: int,
    avg_latency_ms: float,
    cpu_percent: float,
    memory_bytes: int,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateMetricsEntryResponse:
    """Create a metrics entry."""
    if session_id is None:
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    out_ts = await conn.fetchval(
        """
        INSERT INTO metrics_entry (session_id, ts, requests_total, errors_total,
                                   avg_latency_ms, cpu_percent, memory_bytes, mcp)
        VALUES ($1, $2::timestamptz, $3, $4, $5, $6, $7, $8)
        RETURNING ts::text
        """,
        session_id,
        ts,
        requests_total,
        errors_total,
        avg_latency_ms,
        cpu_percent,
        memory_bytes,
        mcp,
    )

    if not out_ts:
        raise ValueError("Failed to create metrics entry")

    return CreateMetricsEntryResponse(ts=out_ts)
