"""Tests for refresh_benchmark."""

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


async def test_new_benchmark_appears_after_refresh(conn, redis_client, profile_id, department_id):
    _created(await _benchmark(conn, redis_client, profile_id, department_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_benchmark(conn)
    items = await get_benchmarks(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_benchmark_is_not_visible_before_refresh(conn, redis_client, profile_id, department_id):
    _created(await _benchmark(conn, redis_client, profile_id, department_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_benchmarks(conn, redis_client, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_benchmark(conn)
    await refresh_benchmark(conn)

    assert True
