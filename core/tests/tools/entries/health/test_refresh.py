"""Tests for refresh_health_internal."""

import pytest

from app.tools.entries.health.refresh import refresh_health_internal

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _Conn:
    def __init__(self):
        self.calls = []

    async def execute(self, query):
        self.calls.append(query)


async def test_executes_refresh_and_invalidates_tags(monkeypatch):
    conn = _Conn()
    invalidated = []

    async def _invalidate(tags, redis=None):
        invalidated.append((tags, redis))

    monkeypatch.setattr("app.tools.entries.health.refresh.get_redis_client", lambda: "redis")
    monkeypatch.setattr("app.tools.entries.health.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.health.refresh.time.time", lambda: 50.0)

    result = await refresh_health_internal(conn)

    assert conn.calls == ["REFRESH MATERIALIZED VIEW CONCURRENTLY health_mv"]
    assert invalidated == [(["entries", "health"], "redis")]
    assert result["success"] is True


async def test_returns_duration_metadata(monkeypatch):
    conn = _Conn()
    values = iter([5.0, 5.2])

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr("app.tools.entries.health.refresh.get_redis_client", lambda: None)
    monkeypatch.setattr("app.tools.entries.health.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.health.refresh.time.time", lambda: next(values))

    result = await refresh_health_internal(conn)

    assert result["duration_ms"] == 200
    assert result["message"] == "Refreshed health_mv in 200ms"


async def test_propagates_execute_errors(monkeypatch):
    class _BrokenConn:
        async def execute(self, query):
            raise RuntimeError("boom")

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr("app.tools.entries.health.refresh.get_redis_client", lambda: None)
    monkeypatch.setattr("app.tools.entries.health.refresh.invalidate_tags", _invalidate)

    with pytest.raises(RuntimeError, match="boom"):
        await refresh_health_internal(_BrokenConn())
