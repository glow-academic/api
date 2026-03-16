"""Tests for search_metrics."""

import pytest

from app.tools.entries.metrics.refresh import refresh_metrics_internal
from app.tools.entries.metrics.search import search_metrics
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _insert_metric(conn, session_id):
    await conn.execute(
        """
        INSERT INTO metrics_entry (ts, requests_total, errors_total,
                                   avg_latency_ms, cpu_percent, memory_bytes, session_id)
        VALUES (NOW(), $1, $2, $3, $4, $5, $6)
        """,
        100,
        5,
        50.0,
        25.0,
        1024000,
        session_id,
    )


async def test_finds_created_entry(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    await _insert_metric(conn, session.id)
    await refresh_metrics_internal(conn)

    items = await search_metrics(conn)

    assert len(items) >= 1


async def test_pagination_limit(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    await _insert_metric(conn, session.id)
    await _insert_metric(conn, session.id)
    await refresh_metrics_internal(conn)

    items = await search_metrics(conn, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    await _insert_metric(conn, session.id)
    await refresh_metrics_internal(conn)

    items = await search_metrics(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    await _insert_metric(conn, session.id)

    items = await search_metrics(conn, bypass_mv=True)

    assert len(items) >= 1
