"""Tests for search_test_grades."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_grade.refresh import refresh_test_grade
from app.tools.entries.test_grade.search import search_test_grades
from app.tools.entries.test_invocation.create import create_test_invocation

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    test_invocation = await create_test_invocation(
        conn, test_id=test.id, call_id=call2.id
    )
    result = await create_test_grade(
        conn,
        invocation_id=test_invocation.id,
        call_id=call2.id,
        run_id=run.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    return result, test_invocation, run


async def test_finds_created_entry(conn, profile_id):
    result, test_invocation, run = await _setup(conn, profile_id)
    await refresh_test_grade(conn)

    items = await search_test_grades(conn, invocation_ids=[test_invocation.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_invocation_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_test_grade(conn)

    items = await search_test_grades(conn, invocation_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_run_id(conn, profile_id):
    result, _, run = await _setup(conn, profile_id)
    await refresh_test_grade(conn)

    items = await search_test_grades(conn, run_ids=[run.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, profile_id):
    result, test_invocation, _ = await _setup(conn, profile_id)
    await refresh_test_grade(conn)

    items = await search_test_grades(conn, invocation_ids=[test_invocation.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_test_grade(conn)

    items = await search_test_grades(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, test_invocation, _ = await _setup(conn, profile_id)

    items = await search_test_grades(
        conn, invocation_ids=[test_invocation.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert result.id in ids
