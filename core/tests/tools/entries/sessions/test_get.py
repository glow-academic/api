"""Tests for get_sessions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_returns_session_by_id(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].profile_id == profile_id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, redis_client, profile_id):
    r1 = await create_session(conn, redis_client, profile_id=profile_id)
    r2 = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await get_sessions(conn, [r1.id, r2.id], redis_client)

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, redis_client, profile_id):
    items = await get_sessions(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client, profile_id):
    items = await get_sessions(conn, [], redis_client)

    assert items == []


async def test_bypass_mv_returns_without_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    items = await get_sessions(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].profile_id == profile_id
