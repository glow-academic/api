"""Tests for create_invocation."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.invocation.create import create_invocation

pytestmark = pytest.mark.asyncio


async def _invocation(conn, **overrides):
    benchmark = await create_benchmark(conn)
    defaults = dict(benchmark_id=benchmark.id)
    defaults.update(overrides)
    result = await create_invocation(conn, **defaults)
    return result, benchmark


async def test_returns_id(conn):
    result, _ = await _invocation(conn)

    assert result.id is not None


async def test_row_exists(conn):
    result, benchmark = await _invocation(conn)

    row = await conn.fetchrow(
        "SELECT benchmark_id FROM invocation_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["benchmark_id"] == benchmark.id


async def test_passes_mcp_flag(conn):
    result, _ = await _invocation(conn, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM invocation_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
