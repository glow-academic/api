"""Tests for search_benchmarks."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.entries.benchmark.search import search_benchmarks

pytestmark = pytest.mark.asyncio


async def _setup(conn):
    result = await create_benchmark(conn)
    return result


async def test_returns_all_without_filter(conn):
    await _setup(conn)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn)

    assert len(items) >= 1


async def test_pagination_limit(conn):
    await _setup(conn)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn, limit=1)

    assert len(items) <= 1


async def test_finds_created_entry(conn):
    result = await _setup(conn)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn)

    benchmark_ids = [item.benchmark_id for item in items]
    assert result.id in benchmark_ids


async def test_bypass_mv_finds_without_refresh(conn):
    result = await _setup(conn)

    items = await search_benchmarks(conn, bypass_mv=True)

    benchmark_ids = [item.benchmark_id for item in items]
    assert result.id in benchmark_ids
