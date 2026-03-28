"""Tests for get_test_invocation_bridge."""

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
from app.tools.entries.test_invocation_bridge.get import get_test_invocation_bridge
from app.tools.entries.test_invocation_bridge.refresh import refresh_test_invocation_bridge
from tests.helpers import nonexistent_id

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


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_test_invocation_bridge(conn, profile_id):
    _created(await _test_invocation_bridge(conn, profile_id))
    await refresh_test_invocation_bridge(conn)
    lookup_id = getattr(created, 'test_invocation_id', None) or getattr(created, 'id', None) or getattr(created, 'test_invocation', None)
    items = await get_test_invocation_bridge(conn, test_invocation_ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_test_invocation_bridge(conn, test_invocation_ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_test_invocation_bridge(conn, test_invocation_ids=[])

    assert items == []
