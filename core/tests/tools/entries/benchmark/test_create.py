"""Tests for create_benchmark."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.get import get_benchmarks
from app.tools.entries.benchmark.refresh import refresh_benchmark

pytestmark = pytest.mark.asyncio


async def _benchmark(conn, profile_id, department_id, **overrides):
    defaults = dict(
        profiles_ids=[profile_id],
        departments_ids=[department_id],
    )
    defaults.update(overrides)
    return await create_benchmark(conn, **defaults)


async def test_returns_id(conn, profile_id, department_id):
    result = await _benchmark(conn, profile_id, department_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, department_id):
    result = await _benchmark(conn, profile_id, department_id)
    await refresh_benchmark(conn)

    items = await get_benchmarks(conn, [result.id])

    assert len(items) == 1
    assert items[0].benchmark_id == result.id
    assert items[0].profile_ids == [profile_id]
    assert items[0].department_ids == [department_id]


async def test_passes_mcp_flag(conn, profile_id, department_id):
    result = await _benchmark(conn, profile_id, department_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM benchmark_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
