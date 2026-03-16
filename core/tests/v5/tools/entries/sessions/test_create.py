"""Tests for create_session."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio


async def test_returns_id(conn, profile_id):
    result = await create_session(conn, profile_id=profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    result = await create_session(conn, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].profile_id == profile_id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, profile_id):
    result = await create_session(
        conn,
        profile_id=profile_id,
        mcp=True,
    )
    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True
