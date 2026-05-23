"""Tests for refresh_sessions."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_new_session_appears_after_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id], redis_client)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_session_not_visible_before_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    items = await get_sessions(conn, [result.id], redis_client)
    assert items == []
