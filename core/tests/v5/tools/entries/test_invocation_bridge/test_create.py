"""Tests for create_test_invocation_bridge."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_bridge.create import (
    create_test_invocation_bridge,
)

pytestmark = pytest.mark.asyncio


async def _test_invocation_bridge(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(
        conn,
        call_id=call.id,
        profiles_id=profile_id,
    )
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    test_invocation = await create_test_invocation(
        conn, test_id=test.id, call_id=call2.id
    )
    benchmark = await create_benchmark(conn, session_id=session.id)
    invocation = await create_invocation(conn, benchmark_id=benchmark.id)
    defaults = dict(
        test_invocation_id=test_invocation.id,
        invocation_id=invocation.id,
        session_id=session.id,
    )
    defaults.update(overrides)
    result = await create_test_invocation_bridge(conn, **defaults)
    return result, test_invocation, invocation


async def test_returns_ids(conn, profile_id):
    result, test_invocation, invocation = await _test_invocation_bridge(
        conn, profile_id
    )

    assert result.test_invocation_id == test_invocation.id
    assert result.invocation_id == invocation.id


async def test_row_exists(conn, profile_id):
    result, _, _ = await _test_invocation_bridge(conn, profile_id)

    row = await conn.fetchrow(
        "SELECT test_invocation_id, invocation_id FROM test_invocation_bridge_entry WHERE test_invocation_id = $1 AND invocation_id = $2",
        result.test_invocation_id,
        result.invocation_id,
    )
    assert row is not None


async def test_passes_mcp_flag(conn, profile_id):
    result, _, _ = await _test_invocation_bridge(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM test_invocation_bridge_entry WHERE test_invocation_id = $1",
        result.test_invocation_id,
    )
    assert row is not None
    assert row["mcp"] is True
