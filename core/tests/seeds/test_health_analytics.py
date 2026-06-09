"""Integration test for the health + metrics analytical seed.

Guards the fix for the empty Health dashboard (``health-overview`` /
``health-status-indicators`` demos): before this seed, the university
template shipped with empty ``health_mv`` / ``metrics_mv``, so
``/system/health`` returned ``total_count: 0`` and the dashboard rendered
a blank "Application Metrics" panel.

The seed writes synthetic ``health_entry`` / ``metrics_entry`` history via
the canonical create black-boxes; after a (non-concurrent) MV refresh —
exactly what the runner does post-seed — the same search black-boxes the
dashboard reads return non-empty service-hourly + metrics-hourly rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import asyncpg
import pytest
from redis.asyncio import Redis

# `database` is a top-level package at the repo root (sibling of `core`),
# not on the path under the `PYTHONPATH=core` test invocation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.tools.entries.health.search import search_health  # noqa: E402
from app.tools.entries.metrics.search import search_metrics  # noqa: E402
from database.seeds.health_analytics import _SERVICES  # noqa: E402
from database.seeds.health_analytics import seed as seed_health_analytics  # noqa: E402


@pytest.mark.asyncio
async def test_health_seed_populates_service_and_metrics_views(
    pool: asyncpg.Pool, redis_client: Redis
) -> None:
    inserted = await seed_health_analytics(pool, redis_client)
    assert inserted > 0, "seed inserted no rows"

    async with pool.acquire() as conn:
        # Non-concurrent refresh mirrors the runner's post-seed refresh and
        # works even though the MVs start out empty (CONCURRENTLY would not).
        await conn.execute("REFRESH MATERIALIZED VIEW health_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW metrics_mv")

        health_rows = await search_health(
            conn, redis_client, limit=1000, bypass_mv=True
        )
        metrics_rows = await search_metrics(
            conn, redis_client, limit=1000, bypass_mv=True
        )

    # service_hourly: every monitored service is represented.
    assert health_rows, "health_mv is empty after seed + refresh"
    seeded_services = {row.service for row in health_rows}
    assert set(_SERVICES) <= seeded_services, (
        f"missing services: {set(_SERVICES) - seeded_services}"
    )

    # metrics_hourly: the Application Metrics panel has data.
    assert metrics_rows, "metrics_mv is empty after seed + refresh"
    assert all(row.sample_count >= 1 for row in metrics_rows)

    # status-indicators: at least one bucket is degraded (a failed check),
    # so the demo shows a realistic non-uniform health state.
    assert any(row.fail_count > 0 for row in health_rows), (
        "expected at least one degraded service bucket for status indicators"
    )
