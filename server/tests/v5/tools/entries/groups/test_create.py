"""Tests for create_group."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id)
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_name(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id, name="test-group")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id])

    assert len(items) == 1
    assert items[0].name == "test-group"


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id, mcp=True)
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True
