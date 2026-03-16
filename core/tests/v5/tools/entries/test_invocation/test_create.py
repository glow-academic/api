"""Tests for create_test_invocation."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.entries.test_invocation.refresh import (
    refresh_test_invocation,
)

pytestmark = pytest.mark.asyncio


async def _test_invocation(conn, profile_id, **overrides):
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
    defaults = dict(test_id=test.id, call_id=call2.id)
    defaults.update(overrides)
    result = await create_test_invocation(conn, **defaults)
    return result, test


async def test_returns_id(conn, profile_id):
    result, _ = await _test_invocation(conn, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    result, test = await _test_invocation(conn, profile_id)
    await refresh_test_invocation(conn)

    items = await get_test_invocations(conn, [result.id])

    assert len(items) == 1
    assert items[0].invocation_id == result.id
    assert items[0].test_id == test.id


async def test_passes_mcp_flag(conn, profile_id):
    result, _ = await _test_invocation(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM test_invocation_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
