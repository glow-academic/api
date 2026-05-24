"""Tests for get_logins."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.logins.create import create_login
from app.tools.entries.logins.get import get_logins
from app.tools.entries.logins.refresh import refresh_logins
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_returns_login_by_id(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_login(conn, redis_client, session_id=session.id)
    await refresh_logins(conn)

    items = await get_logins(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    r1 = await create_login(conn, redis_client, session_id=session.id)
    r2 = await create_login(conn, redis_client, session_id=session.id)
    await refresh_logins(conn)

    items = await get_logins(conn, [r1.id, r2.id], redis_client)

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, redis_client, profile_id):
    items = await get_logins(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client, profile_id):
    items = await get_logins(conn, [], redis_client)

    assert items == []


async def test_bypass_mv_returns_without_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_login(conn, redis_client, session_id=session.id)

    items = await get_logins(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
