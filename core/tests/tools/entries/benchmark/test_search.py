"""Tests for search_benchmarks."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.entries.benchmark.search import search_benchmarks

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client):
    result = await create_benchmark(conn, redis_client)
    return result


async def test_returns_all_without_filter(conn, redis_client):
    await _setup(conn, redis_client)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn, redis_client)

    assert len(items) >= 1


async def test_pagination_limit(conn, redis_client):
    await _setup(conn, redis_client)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn, redis_client, limit=1)

    assert len(items) <= 1


async def test_finds_created_entry(conn, redis_client):
    result = await _setup(conn, redis_client)
    await refresh_benchmark(conn)

    items = await search_benchmarks(conn, redis_client)

    benchmark_ids = [item.benchmark_id for item in items]
    assert result.id in benchmark_ids


async def test_bypass_mv_finds_without_refresh(conn, redis_client):
    result = await _setup(conn, redis_client)

    items = await search_benchmarks(conn, redis_client, bypass_mv=True)

    benchmark_ids = [item.benchmark_id for item in items]
    assert result.id in benchmark_ids
