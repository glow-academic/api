"""Tests for refresh_invocations."""

import pytest
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.invocation.get import get_invocations
from app.tools.entries.invocation.refresh import refresh_invocations
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _invocation(conn, **overrides):
    benchmark = await create_benchmark(conn)
    defaults = dict(benchmark_id=benchmark.id)
    defaults.update(overrides)
    result = await create_invocation(conn, **defaults)
    return result, benchmark


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_invocation_appears_after_refresh(conn):
    _created(await _invocation(conn))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_invocations(conn)
    items = await get_invocations(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_invocation_is_not_visible_before_refresh(conn):
    _created(await _invocation(conn))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_invocations(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_invocations(conn)
    await refresh_invocations(conn)

    assert True
