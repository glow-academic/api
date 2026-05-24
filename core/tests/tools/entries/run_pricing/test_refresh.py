"""Tests for refresh_run_pricing_internal."""

import pytest

from app.tools.entries.run_pricing.refresh import refresh_run_pricing_internal

pytestmark = pytest.mark.asyncio


class _Conn:
    def __init__(self):
        self.calls = []

    async def execute(self, query):
        self.calls.append(query)


async def test_executes_refresh_statement():
    conn = _Conn()

    await refresh_run_pricing_internal(conn)

    assert conn.calls == ["REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv"]


async def test_can_be_called_twice():
    conn = _Conn()

    await refresh_run_pricing_internal(conn)
    await refresh_run_pricing_internal(conn)

    assert len(conn.calls) == 2


async def test_propagates_execute_errors():
    class _BrokenConn:
        async def execute(self, query):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await refresh_run_pricing_internal(_BrokenConn())
