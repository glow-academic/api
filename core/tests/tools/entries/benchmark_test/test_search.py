"""Tests for search_benchmark_tests."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.benchmark_test.refresh import refresh_benchmark_test
from app.tools.entries.benchmark_test.search import search_benchmark_tests
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    benchmark = await create_benchmark(conn, redis_client, session_id=session.id)
    test = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    result = await create_benchmark_test(
        conn, redis_client, benchmark_id=benchmark.id, test_id=test.id, session_id=session.id
    )
    return result, benchmark, test


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, benchmark, _ = await _setup(conn, redis_client, profile_id)
    await refresh_benchmark_test(conn)

    items = await search_benchmark_tests(conn, redis_client, benchmark_ids=[benchmark.id])

    pairs = [(item.benchmark_id, item.test_id) for item in items]
    assert (result.benchmark_id, result.test_id) in pairs


async def test_filters_by_benchmark_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_benchmark_test(conn)

    items = await search_benchmark_tests(conn, redis_client, benchmark_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_test_id(conn, redis_client, profile_id):
    result, _, test = await _setup(conn, redis_client, profile_id)
    await refresh_benchmark_test(conn)

    items = await search_benchmark_tests(conn, redis_client, test_ids=[test.id])

    pairs = [(item.benchmark_id, item.test_id) for item in items]
    assert (result.benchmark_id, result.test_id) in pairs


async def test_pagination_limit(conn, redis_client, profile_id):
    _, benchmark, _ = await _setup(conn, redis_client, profile_id)
    await refresh_benchmark_test(conn)

    items = await search_benchmark_tests(conn, redis_client, benchmark_ids=[benchmark.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_benchmark_test(conn)

    items = await search_benchmark_tests(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, benchmark, _ = await _setup(conn, redis_client, profile_id)

    items = await search_benchmark_tests(
        conn, redis_client, benchmark_ids=[benchmark.id], bypass_mv=True
    )

    pairs = [(item.benchmark_id, item.test_id) for item in items]
    assert (result.benchmark_id, result.test_id) in pairs
