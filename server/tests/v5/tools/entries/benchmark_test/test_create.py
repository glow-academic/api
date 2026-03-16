"""Tests for create_benchmark_test."""

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


async def test_returns_ids(conn, profile_id):
    result, benchmark, test = await _benchmark_test(conn, profile_id)

    assert result.benchmark_id == benchmark.id
    assert result.test_id == test.id


async def test_row_exists(conn, profile_id):
    result, _, _ = await _benchmark_test(conn, profile_id)

    row = await conn.fetchrow(
        "SELECT benchmark_id, test_id FROM benchmark_test_entry WHERE benchmark_id = $1",
        result.benchmark_id,
    )
    assert row is not None
    assert row["test_id"] == result.test_id


async def test_visible_via_get_after_refresh(conn, profile_id):
    result, _, _ = await _benchmark_test(conn, profile_id)
    await refresh_benchmark_test(conn)

    items = await get_benchmark_tests(conn, [result.benchmark_id])
    assert len(items) == 1


async def test_passes_mcp_flag(conn, profile_id):
    result, _, _ = await _benchmark_test(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM benchmark_test_entry WHERE benchmark_id = $1",
        result.benchmark_id,
    )
    assert row is not None
    assert row["mcp"] is True
