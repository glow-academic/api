"""Tests for get_benchmarks."""

import pytest
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.get import get_benchmarks
from app.tools.entries.benchmark.refresh import refresh_benchmark
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _benchmark(conn, redis_client, profile_id, department_id, **overrides):
    defaults = dict(
        profiles_ids=[profile_id],
        departments_ids=[department_id],
    )
    defaults.update(overrides)
    return await create_benchmark(conn, redis_client, **defaults)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_benchmark(conn, redis_client, profile_id, department_id):
    _created(await _benchmark(conn, redis_client, profile_id, department_id))
    await refresh_benchmark(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_benchmarks(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_benchmarks(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_benchmarks(conn, ids=[], redis=redis_client)

    assert items == []
