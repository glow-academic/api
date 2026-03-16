"""Tests for create_problem."""

import pytest

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


async def test_returns_id(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="bug"
    )

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
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
    assert items[0].message == "No message provided"
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_custom_message(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn,
        session_id=session.id,
        call_id=call.id,
        type="feature",
        message="Custom message",
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [result.id])

    assert len(items) == 1
    assert items[0].message == "Custom message"
    assert items[0].type == "feature"


async def test_passes_mcp_flag(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn, session_id=session.id, call_id=call.id, type="bug", mcp=True
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True


async def test_links_profile(conn, profile_id):
    session, call = await _call(conn, profile_id)
    result = await create_problem(
        conn,
        session_id=session.id,
        call_id=call.id,
        type="question",
        profile_id=profile_id,
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [result.id])

    assert len(items) == 1
    assert items[0].profile_id == profile_id
