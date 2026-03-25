"""Tests for create_resolve."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.resolves.get import get_resolves
from app.tools.entries.resolves.refresh import refresh_resolves
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _call(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    return session, call


async def _problem(conn, session, call):
    result = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="bug"
    )
    return result.id


async def test_returns_id(conn, profile_id):
    session, call = await _call(conn, profile_id)
    problem_id = await _problem(conn, session, call)
    result = await create_resolve(
        conn, problem_id=problem_id, resolved=False, call_id=call.id
    )

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    session, call = await _call(conn, profile_id)
    problem_id = await _problem(conn, session, call)
    result = await create_resolve(
        conn, problem_id=problem_id, resolved=True, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].problem_id == problem_id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_resolved_flag(conn, profile_id):
    session, call = await _call(conn, profile_id)
    problem_id = await _problem(conn, session, call)
    result = await create_resolve(
        conn, problem_id=problem_id, resolved=True, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id])

    assert len(items) == 1
    assert items[0].resolved is True


async def test_passes_mcp_flag(conn, profile_id):
    session, call = await _call(conn, profile_id)
    problem_id = await _problem(conn, session, call)
    result = await create_resolve(
        conn, problem_id=problem_id, resolved=False, call_id=call.id, mcp=True
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True


async def test_passes_call_id(conn, profile_id):
    session, call = await _call(conn, profile_id)
    problem_id = await _problem(conn, session, call)

    result = await create_resolve(
        conn, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id])

    assert len(items) == 1
    assert items[0].call_id == call.id
