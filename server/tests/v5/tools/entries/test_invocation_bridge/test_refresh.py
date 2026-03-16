"""Tests for refresh_test_invocation_bridge."""

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
from app.tools.entries.test_invocation_bridge.get import (
    get_test_invocation_bridge,
)
from app.tools.entries.test_invocation_bridge.refresh import (
    refresh_test_invocation_bridge,
)

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
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
    return await create_test_invocation_bridge(
        conn,
        test_invocation_id=test_invocation.id,
        invocation_id=invocation.id,
        session_id=session.id,
    )


async def test_appears_after_refresh(conn, profile_id):
    result = await _setup(conn, profile_id)
    await refresh_test_invocation_bridge(conn)

    items = await get_test_invocation_bridge(
        conn, test_invocation_ids=[result.test_invocation_id]
    )
    assert len(items) >= 1


async def test_not_visible_before_refresh(conn, profile_id):
    result = await _setup(conn, profile_id)

    items = await get_test_invocation_bridge(
        conn, test_invocation_ids=[result.test_invocation_id]
    )
    assert len(items) == 0
