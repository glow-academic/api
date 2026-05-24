"""Tests for search_tests."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test.refresh import refresh_test
from app.tools.entries.test.search import search_tests

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    result = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    return result, profile_id


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, pid = await _setup(conn, redis_client, profile_id)
    await refresh_test(conn)

    items, total_count = await search_tests(conn, redis_client, profile_ids=[pid])

    ids = [item.test_id for item in items]
    assert total_count >= 1
    assert result.id in ids


async def test_filters_by_profile_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_test(conn)

    items, total_count = await search_tests(conn, redis_client, profile_ids=[nonexistent_id()])

    assert items == []
    assert total_count == 0


async def test_filters_by_eval_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_test(conn)

    items, total_count = await search_tests(conn, redis_client, eval_ids=[nonexistent_id()])

    assert items == []
    assert total_count == 0


async def test_pagination_limit(conn, redis_client, profile_id):
    result, pid = await _setup(conn, redis_client, profile_id)
    await refresh_test(conn)

    items, total_count = await search_tests(conn, redis_client, profile_ids=[pid], limit=1)

    assert total_count >= 1
    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_test(conn)

    items, total_count = await search_tests(conn, redis_client)

    assert total_count >= 1
    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, pid = await _setup(conn, redis_client, profile_id)

    items, total_count = await search_tests(conn, redis_client, profile_ids=[pid], bypass_mv=True)

    ids = [item.test_id for item in items]
    assert total_count >= 1
    assert result.id in ids
