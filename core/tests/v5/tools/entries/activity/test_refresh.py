"""Tests for refresh_activity."""

import pytest

from app.tools.entries.activity.create import create_activity
from app.tools.entries.activity.get import get_activity
from app.tools.entries.activity.refresh import refresh_activity
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_new_activity_appears_after_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(conn, session_id=session.id)
    await refresh_activity(conn)

    items = await get_activity(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_activity_not_visible_before_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(conn, session_id=session.id)

    items = await get_activity(conn, [result.id])

    assert items == []
