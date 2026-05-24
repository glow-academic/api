"""Tests for refresh_upload_completion."""

import pytest

from app.tools.entries.upload_completion.refresh import refresh_upload_completion

pytestmark = pytest.mark.asyncio


class _Conn:
    def __init__(self):
        self.calls = []

    async def execute(self, query):
        self.calls.append(query)


async def test_executes_refresh_statement():
    conn = _Conn()

    await refresh_upload_completion(conn)

    assert conn.calls == ["REFRESH MATERIALIZED VIEW CONCURRENTLY upload_completion_mv"]


async def test_can_be_called_multiple_times():
    conn = _Conn()

    await refresh_upload_completion(conn)
    await refresh_upload_completion(conn)

    assert len(conn.calls) == 2


async def test_propagates_execute_errors():
    class _BrokenConn:
        async def execute(self, query):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await refresh_upload_completion(_BrokenConn())
