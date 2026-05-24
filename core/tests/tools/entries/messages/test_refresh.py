"""Tests for refresh_messages_internal."""

import pytest

from app.tools.entries.messages.refresh import refresh_messages_internal

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _Conn:
    def __init__(self):
        self.calls = []

    async def execute(self, query):
        self.calls.append(query)


async def test_executes_refresh_statement(monkeypatch):
    conn = _Conn()
    invalidated = []

    async def _invalidate(tags, redis=None):
        invalidated.append((tags, redis))

    monkeypatch.setattr(
        "app.tools.entries.messages.refresh.get_redis_client",
        lambda: "redis",
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.messages.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.messages.refresh.time.time", lambda: 100.0)

    result = await refresh_messages_internal(conn)

    assert conn.calls == ["REFRESH MATERIALIZED VIEW CONCURRENTLY messages_mv"]
    assert invalidated == [(["entries", "messages"], "redis")]
    assert result["success"] is True


async def test_returns_duration_and_message(monkeypatch):
    conn = _Conn()
    values = iter([100.0, 100.125])

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr(
        "app.tools.entries.messages.refresh.get_redis_client",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.messages.refresh.invalidate_tags", _invalidate)
    monkeypatch.setattr("app.tools.entries.messages.refresh.time.time", lambda: next(values))

    result = await refresh_messages_internal(conn)

    assert result["duration_ms"] == 125
    assert result["message"] == "Refreshed messages_mv in 125ms"


async def test_propagates_execute_errors(monkeypatch):
    class _BrokenConn:
        async def execute(self, query):
            raise RuntimeError("boom")

    async def _invalidate(tags, redis=None):
        return None

    monkeypatch.setattr(
        "app.tools.entries.messages.refresh.get_redis_client",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr("app.tools.entries.messages.refresh.invalidate_tags", _invalidate)

    with pytest.raises(RuntimeError, match="boom"):
        await refresh_messages_internal(_BrokenConn())
