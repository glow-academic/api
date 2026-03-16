"""Write metrics and health snapshots to the database.

Composes black-box entry tools (create_metrics_entry_internal, create_health)
with system session resolution. Called by the metrics collector.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg

from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.types import CreateMetricsEntryResponse


async def write_metrics_snapshot(
    pool: asyncpg.Pool,
    *,
    ts: datetime,
    requests_total: int,
    errors_total: int,
    avg_latency_ms: float,
    cpu_percent: float,
    memory_bytes: int,
) -> CreateMetricsEntryResponse:
    """Write a metrics snapshot to the database."""
    from app.infra.identity.resolve_identity import get_system_session_id

    async with pool.acquire() as conn:
        async with conn.transaction():
            session_id = await get_system_session_id(conn)

            return await create_metrics_entry_internal(
                conn,
                ts=ts,
                requests_total=requests_total,
                errors_total=errors_total,
                avg_latency_ms=avg_latency_ms,
                cpu_percent=cpu_percent,
                memory_bytes=memory_bytes,
                session_id=session_id,
            )


async def write_health_checks(
    pool: asyncpg.Pool,
    *,
    ts: datetime,
    checks: dict,
) -> None:
    """Write health check results to the database."""
    from app.infra.identity.resolve_identity import get_system_session_id
    from app.tools.entries.health.create import create_health

    async with pool.acquire() as conn:
        async with conn.transaction():
            session_id = await get_system_session_id(conn)

            for service, result in checks.items():
                await create_health(
                    conn,
                    service=service,
                    ok=result.ok,
                    latency_ms=result.latency_ms,
                    ts=ts,
                    error=result.error,
                    session_id=session_id,
                )
