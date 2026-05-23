"""Tests for create_group."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_returns_id(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_name(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, name="test-group", artifact_type="persona")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].name == "test-group"


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, mcp=True, artifact_type="persona")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].mcp is True
