"""Health export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search tools — full dump of health, metrics
  3. No resource hydration needed (raw metrics data)
  4. ZIP generation (health.csv + metrics.csv) + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import zipfile
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.health.search import search_health
from app.tools.entries.metrics.search import search_metrics

HEALTH_CSV_COLUMNS = [
    "date_hour",
    "service",
    "check_count",
    "ok_count",
    "fail_count",
    "uptime_percent",
    "avg_latency_ms",
    "min_latency_ms",
    "max_latency_ms",
    "latest_ok",
    "latest_error",
]

METRICS_CSV_COLUMNS = [
    "date_hour",
    "sample_count",
    "avg_cpu_percent",
    "min_cpu_percent",
    "max_cpu_percent",
    "avg_latency_ms",
    "min_latency_ms",
    "max_latency_ms",
    "avg_memory_bytes",
    "min_memory_bytes",
    "max_memory_bytes",
    "max_requests_total",
    "max_errors_total",
]


async def export_health_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
) -> dict:
    """Health full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Parallel search health + metrics (full dump, no pagination)
      3. No resource hydration needed (raw metrics data)
      4. Generate ZIP (health.csv + metrics.csv) and return base64-encoded content
    """
    from fastapi import HTTPException

    from app.infra.health.types import ExportHealthApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel search all entry types (full dump) --

    async def _fetch_health() -> list:
        async with pool.acquire() as conn:
            return await search_health(conn, limit=100000, offset=0)

    async def _fetch_metrics() -> list:
        async with pool.acquire() as conn:
            return await search_metrics(conn, limit=100000, offset=0)

    (
        health_entries,
        metrics_entries,
    ) = await asyncio.gather(
        _fetch_health(),
        _fetch_metrics(),
    )

    if not health_entries and not metrics_entries:
        return ExportHealthApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: No resource hydration needed --

    # -- Step 4: Generate ZIP + upload --

    # Generate health CSV
    health_output = io.StringIO()
    health_writer = csv.writer(health_output)
    health_writer.writerow(HEALTH_CSV_COLUMNS)

    for h in health_entries:
        health_writer.writerow(
            [
                str(h.date_hour),
                h.service,
                str(h.check_count),
                str(h.ok_count),
                str(h.fail_count),
                str(h.uptime_percent),
                str(h.avg_latency_ms),
                str(h.min_latency_ms),
                str(h.max_latency_ms),
                "Yes" if h.latest_ok else "No",
                h.latest_error,
            ]
        )

    # Generate metrics CSV
    metrics_output = io.StringIO()
    metrics_writer = csv.writer(metrics_output)
    metrics_writer.writerow(METRICS_CSV_COLUMNS)

    for m in metrics_entries:
        metrics_writer.writerow(
            [
                str(m.date_hour),
                str(m.sample_count),
                str(m.avg_cpu_percent),
                str(m.min_cpu_percent),
                str(m.max_cpu_percent),
                str(m.avg_latency_ms),
                str(m.min_latency_ms),
                str(m.max_latency_ms),
                str(m.avg_memory_bytes),
                str(m.min_memory_bytes),
                str(m.max_memory_bytes),
                str(m.max_requests_total),
                str(m.max_errors_total),
            ]
        )

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("health.csv", health_output.getvalue())
        zf.writestr("metrics.csv", metrics_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(health_entries) + len(metrics_entries)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"health_export_{timestamp}.zip"

    return ExportHealthApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
