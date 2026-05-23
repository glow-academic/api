"""Tests for search_test_archives."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_archive.create import create_test_archive
from app.tools.entries.test_archive.refresh import refresh_test_archive
from app.tools.entries.test_archive.search import search_test_archives

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    test = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    result = await create_test_archive(
        conn, redis_client, test_id=test.id, call_id=call.id, archived=True
    )
    return result, test


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, test = await _setup(conn, redis_client, profile_id)
    await refresh_test_archive(conn)

    items = await search_test_archives(conn, redis_client, test_ids=[test.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_test_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_test_archive(conn)

    items = await search_test_archives(conn, redis_client, test_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, test = await _setup(conn, redis_client, profile_id)
    await refresh_test_archive(conn)

    items = await search_test_archives(conn, redis_client, test_ids=[test.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_test_archive(conn)

    items = await search_test_archives(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, test = await _setup(conn, redis_client, profile_id)

    items = await search_test_archives(conn, redis_client, test_ids=[test.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
