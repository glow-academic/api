"""Tests for search_messages."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    result = await create_message(conn, redis_client, run_id=run.id, role="user")
    return result, run


async def _refresh_mv(conn):
    """Refresh messages_mv directly (avoids redis dependency)."""
    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, run = await _setup(conn, redis_client, profile_id)
    await _refresh_mv(conn)

    items, _total_count = await search_messages(conn, redis_client, run_ids=[run.id])

    ids = [item.message_id for item in items]
    assert result.id in ids


async def test_filters_by_run_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await _refresh_mv(conn)

    items, _total_count = await search_messages(conn, redis_client, run_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_role(conn, redis_client, profile_id):
    result, run = await _setup(conn, redis_client, profile_id)
    await _refresh_mv(conn)

    items, _total_count = await search_messages(
        conn, redis_client, run_ids=[run.id], role="assistant"
    )

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, run = await _setup(conn, redis_client, profile_id)
    await _refresh_mv(conn)

    items, _total_count = await search_messages(conn, redis_client, run_ids=[run.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await _refresh_mv(conn)

    items, _total_count = await search_messages(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, run = await _setup(conn, redis_client, profile_id)

    items, _total_count = await search_messages(conn, redis_client, run_ids=[run.id], bypass_mv=True)

    ids = [item.message_id for item in items]
    assert result.id in ids
