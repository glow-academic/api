"""Tests for get_benchmark_tests."""

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


async def _benchmark_test(conn, redis_client, profile_id, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    benchmark = await create_benchmark(conn, redis_client, session_id=session.id)
    test = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    defaults = dict(
        benchmark_id=benchmark.id,
        test_id=test.id,
        session_id=session.id,
    )
    defaults.update(overrides)
    result = await create_benchmark_test(conn, redis_client, **defaults)
    return result, benchmark, test


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_benchmark_test(conn, redis_client, profile_id):
    _created(await _benchmark_test(conn, redis_client, profile_id))
    await refresh_benchmark_test(conn)
    lookup_id = getattr(created, 'benchmark_id', None) or getattr(created, 'id', None) or getattr(created, 'benchmark', None)
    items = await get_benchmark_tests(conn, benchmark_ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_benchmark_tests(conn, benchmark_ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_benchmark_tests(conn, benchmark_ids=[], redis=redis_client)

    assert items == []
