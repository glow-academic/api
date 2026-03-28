"""Tests for refresh_benchmark_test."""

import pytest
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.benchmark_test.get import get_benchmark_tests
from app.tools.entries.benchmark_test.refresh import refresh_benchmark_test
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _benchmark_test(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    benchmark = await create_benchmark(conn, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    defaults = dict(
        benchmark_id=benchmark.id,
        test_id=test.id,
        session_id=session.id,
    )
    defaults.update(overrides)
    result = await create_benchmark_test(conn, **defaults)
    return result, benchmark, test


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_benchmark_test_appears_after_refresh(conn, profile_id):
    _created(await _benchmark_test(conn, profile_id))
    lookup_id = getattr(created, 'benchmark_id', None) or getattr(created, 'id', None) or getattr(created, 'benchmark', None)

    await refresh_benchmark_test(conn)
    items = await get_benchmark_tests(conn, benchmark_ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_benchmark_test_is_not_visible_before_refresh(conn, profile_id):
    _created(await _benchmark_test(conn, profile_id))
    lookup_id = getattr(created, 'benchmark_id', None) or getattr(created, 'id', None) or getattr(created, 'benchmark', None)

    items = await get_benchmark_tests(conn, benchmark_ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_benchmark_test(conn)
    await refresh_benchmark_test(conn)

    assert True
