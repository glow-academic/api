"""Tests for refresh_sessions."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio


async def test_new_session_appears_after_refresh(conn, profile_id):
    result = await create_session(conn, profile_id=profile_id)

    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id])
    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_session_not_visible_before_refresh(conn, profile_id):
    result = await create_session(conn, profile_id=profile_id)

    items = await get_sessions(conn, [result.id])
    assert items == []
