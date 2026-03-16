"""Tests for create_health."""

import pytest

from app.tools.entries.health.create import create_health
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_create_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_health(
        conn, service="api", ok=True, latency_ms=12.5, session_id=session.id
    )

    assert result.id is not None


async def test_roundtrip_via_db(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_health(
        conn,
        service="api",
        ok=True,
        latency_ms=12.5,
        error="none",
        session_id=session.id,
    )

    row = await conn.fetchrow("SELECT * FROM health_entry WHERE id = $1", result.id)

    assert row is not None
    assert row["id"] == result.id
    assert row["service"] == "api"
    assert row["ok"] is True
    assert row["latency_ms"] == 12.5
    assert row["error"] == "none"
    assert row["active"] is True
    assert row["mcp"] is False
    assert row["generated"] is True


async def test_defaults(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_health(
        conn, service="db", ok=False, latency_ms=100.0, session_id=session.id
    )

    row = await conn.fetchrow("SELECT * FROM health_entry WHERE id = $1", result.id)

    assert row is not None
    assert row["ts"] is not None
    assert row["error"] == ""
