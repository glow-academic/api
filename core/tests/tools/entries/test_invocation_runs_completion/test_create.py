"""Tests for create_test_invocation_runs_completion."""

import pytest

from app.tools.entries.test_invocation_runs_completion.create import create_test_invocation_runs_completion
from app.tools.entries.test_invocation_runs_completion.refresh import refresh_test_invocation_runs_completion
from app.tools.entries.test_invocation_runs_completion.refresh import MV_NAME
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test_invocation_runss.create import create_test_invocation_runs

pytestmark = pytest.mark.asyncio


async def _setup_entry(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    seed = await create_test_invocation_runs(conn, session_id=session.id)
    return session, call, seed


async def test_create_returns_id(conn, profile_id):
    session, call, seed = await _setup_entry(conn, profile_id)
    result = await create_test_invocation_runs_completion(conn, test_invocation_runs_id=seed.id, call_id=call.id)

    assert result.id is not None


async def test_row_not_visible_before_refresh(conn, profile_id):
    session, call, seed = await _setup_entry(conn, profile_id)
    result = await create_test_invocation_runs_completion(conn, test_invocation_runs_id=seed.id, call_id=call.id)

    row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is None


async def test_refresh_exposes_created_row(conn, profile_id):
    session, call, seed = await _setup_entry(conn, profile_id)
    result = await create_test_invocation_runs_completion(conn, test_invocation_runs_id=seed.id, call_id=call.id, mcp=True)
    await refresh_test_invocation_runs_completion(conn)

    row = await conn.fetchrow(f"SELECT id, mcp FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is not None
    assert row['id'] == result.id
    assert row['mcp'] is True
