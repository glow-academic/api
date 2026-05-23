"""Tests for create_session."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_returns_id(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].profile_id == profile_id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    result = await create_session(
        conn,
        redis_client, profile_id=profile_id,
        mcp=True,
    )
    await refresh_sessions(conn)

    items = await get_sessions(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].mcp is True
