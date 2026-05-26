"""Write metrics and health snapshots to the database.

Composes black-box entry tools (create_metrics_entry_internal, create_health)
with system session resolution. Called by the metrics collector.

``redis`` is an injected boundary — callers (lifespan-managed code in
``core/app/infra/metrics/collector.py``) pass ``get_redis_client()``;
tests pass the testcontainers-backed ``redis_client`` fixture. This keeps
these writers testable without standing up the FastAPI lifespan.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.types import CreateMetricsEntryResponse


async def write_metrics_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
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
            session_id = await get_system_session_id(conn, redis)

            return await create_metrics_entry_internal(
                conn,
                redis,
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
    redis: Redis,
    *,
    ts: datetime,
    checks: dict,
) -> None:
    """Write health check results to the database."""
    from app.infra.identity.resolve_identity import get_system_session_id
    from app.tools.entries.health.create import create_health

    async with pool.acquire() as conn:
        async with conn.transaction():
            session_id = await get_system_session_id(conn, redis)

            for service, result in checks.items():
                await create_health(
                    conn,
                    redis,
                    service=service,
                    ok=result.ok,
                    latency_ms=result.latency_ms,
                    ts=ts,
                    error=result.error,
                    session_id=session_id,
                )
