"""Tests for metrics entry."""

from datetime import UTC, datetime

import pytest

from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_create_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)

    entry_id = await conn.fetchval(
        "INSERT INTO metrics_entry (ts, requests_total, errors_total, avg_latency_ms, cpu_percent, memory_bytes, session_id) VALUES (NOW(), $1, $2, $3, $4, $5, $6) RETURNING id",
        100,
        5,
        50.0,
        25.0,
        1024000,
        session.id,
    )

    assert entry_id is not None


async def test_roundtrip_via_db(conn, profile_id):
    session = await _session(conn, profile_id)

    entry_id = await conn.fetchval(
        "INSERT INTO metrics_entry (ts, requests_total, errors_total, avg_latency_ms, cpu_percent, memory_bytes, session_id) VALUES (NOW(), $1, $2, $3, $4, $5, $6) RETURNING id",
        100,
        5,
        50.0,
        25.0,
        1024000,
        session.id,
    )

    row = await conn.fetchrow("SELECT * FROM metrics_entry WHERE id = $1", entry_id)

    assert row is not None
    assert row["id"] == entry_id
    assert row["requests_total"] == 100
    assert row["errors_total"] == 5
    assert row["avg_latency_ms"] == 50.0
    assert row["cpu_percent"] == 25.0
    assert row["memory_bytes"] == 1024000
    assert row["session_id"] == session.id
    assert row["active"] is True
    assert row["mcp"] is False


async def test_create_metrics_entry_internal_with_datetime(pool):
    """Verify create_metrics_entry_internal accepts a datetime object (not a string)."""
    ts = datetime(2031, 1, 1, 10, 0, tzinfo=UTC)

    async with pool.acquire() as conn:
        result = await create_metrics_entry_internal(
            conn,
            ts=ts,
            requests_total=100,
            errors_total=2,
            avg_latency_ms=45.5,
            cpu_percent=33.3,
            memory_bytes=123456,
        )

    assert result.ts is not None
