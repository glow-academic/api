"""Tests for create_activity."""

import pytest

from app.tools.entries.activity.create import create_activity
from app.tools.entries.activity.get import get_activity
from app.tools.entries.activity.refresh import refresh_activity
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(conn, session_id=session.id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(conn, session_id=session.id)
    await refresh_activity(conn)

    items = await get_activity(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(conn, session_id=session.id, mcp=True)
    await refresh_activity(conn)

    items = await get_activity(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True


async def test_links_profile(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_activity(
        conn,
        session_id=session.id,
        profile_id=profile_id,
    )
    await refresh_activity(conn)

    items = await get_activity(conn, [result.id])

    assert len(items) == 1
    assert items[0].profile_id == profile_id
