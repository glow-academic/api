"""Tests for refresh_uploads_internal."""

import pytest

from app.tools.entries.uploads.refresh import refresh_uploads_internal

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

    monkeypatch.setattr(
        "app.tools.entries.uploads.refresh.get_redis_client",
        lambda: "redis",
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.uploads.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.uploads.refresh.time.time", lambda: 10.0)

    result = await refresh_uploads_internal(conn)

    assert conn.calls == ["REFRESH MATERIALIZED VIEW CONCURRENTLY uploads_mv"]
    assert invalidated == [(["entries", "uploads"], "redis")]
    assert result["success"] is True


async def test_returns_duration_metadata(monkeypatch):
    conn = _Conn()
    values = iter([1.0, 1.06])

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr(
        "app.tools.entries.uploads.refresh.get_redis_client",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.uploads.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.uploads.refresh.time.time", lambda: next(values))

    result = await refresh_uploads_internal(conn)

    assert result["duration_ms"] == 60
    assert result["message"] == "Refreshed uploads_mv in 60ms"


async def test_propagates_execute_errors(monkeypatch):
    class _BrokenConn:
        async def execute(self, query):
            raise RuntimeError("boom")

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr(
        "app.tools.entries.uploads.refresh.get_redis_client",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.uploads.refresh.invalidate_tags", _invalidate)

    with pytest.raises(RuntimeError, match="boom"):
        await refresh_uploads_internal(_BrokenConn())
