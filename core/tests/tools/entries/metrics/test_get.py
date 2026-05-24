"""Tests for get_metrics."""

from datetime import UTC, datetime

import pytest

from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.get import get_metrics
from app.tools.entries.metrics.refresh import refresh_metrics_internal
from app.tools.entries.metrics.search import search_metrics

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_gets_created_metric_hour(conn, redis_client):
    ts = datetime(2031, 1, 1, 10, 15, tzinfo=UTC)
    await create_metrics_entry_internal(
        conn,
        redis_client, ts=ts,
        requests_total=120,
        errors_total=3,
        avg_latency_ms=40.5,
        cpu_percent=22.0,
        memory_bytes=2048,
    )
    await refresh_metrics_internal(conn)

    summary = (await search_metrics(conn, redis_client))[0]
    items = await get_metrics(conn, [summary.date_hour], redis_client)

    assert len(items) == 1
    assert items[0].date_hour == summary.date_hour
    assert items[0].max_requests_total == 120


async def test_returns_empty_for_missing_hour(conn, redis_client):
    items = await get_metrics(conn, [datetime(2035, 1, 1, tzinfo=UTC)], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_metrics(conn, [], redis_client)

    assert items == []
