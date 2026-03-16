"""Tests for search_test_invocation_entries_internal."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_completion.create import (
    create_test_invocation_completion,
)

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    invocation_call = await create_call(conn, run_id=run.id, session_id=session.id)
    result = await create_test_invocation(
        conn,
        test_id=test.id,
        call_id=invocation_call.id,
    )
    return result, test, invocation_call


async def test_finds_created_entry(conn, profile_id):
    result, test, _invocation_call = await _setup(conn, profile_id)
    await refresh_test_invocation(conn)

    items, _total_count = await search_test_invocation_entries_internal(
        conn, test_ids=[test.id]
    )

    ids = [item.invocation_id for item in items]
    assert result.id in ids


async def test_filters_by_test_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_test_invocation(conn)

    items, _total_count = await search_test_invocation_entries_internal(
        conn, test_ids=[nonexistent_id()]
    )

    assert items == []


async def test_pagination_limit(conn, profile_id):
    result, test, _invocation_call = await _setup(conn, profile_id)
    await refresh_test_invocation(conn)

    items, _total_count = await search_test_invocation_entries_internal(
        conn, test_ids=[test.id], limit=1
    )

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_test_invocation(conn)

    items, _total_count = await search_test_invocation_entries_internal(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, test, _invocation_call = await _setup(conn, profile_id)

    items, _total_count = await search_test_invocation_entries_internal(
        conn, test_ids=[test.id], bypass_mv=True
    )

    ids = [item.invocation_id for item in items]
    assert result.id in ids


async def test_completion_marks_invocation_completed(conn, profile_id):
    result, test, invocation_call = await _setup(conn, profile_id)
    completion = await create_test_invocation_completion(
        conn,
        invocation_id=result.id,
        call_id=invocation_call.id,
    )
    await refresh_test_invocation(conn)

    items, _total_count = await search_test_invocation_entries_internal(
        conn,
        test_ids=[test.id],
    )

    match = next(item for item in items if item.invocation_id == result.id)
    assert completion.id is not None
    assert match.invocation_completed is True
