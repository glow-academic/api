"""Tests for get_problems."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.problems.get import get_problems
from app.tools.entries.problems.refresh import refresh_problems
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _call(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    return session, call


async def test_returns_problem_by_id(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="bug"
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].type == "bug"
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, profile_id):
    session, call = await _call(conn, profile_id)
    r1 = await create_problem(conn, session_id=session.id, call_id=call.id, type="bug")
    r2 = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="feature"
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [r1.id, r2.id])

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, profile_id):
    items = await get_problems(conn, [nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, profile_id):
    items = await get_problems(conn, [])

    assert items == []


async def test_bypass_mv_returns_without_refresh(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="other"
    )

    items = await get_problems(conn, [result.id], bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].type == "other"
