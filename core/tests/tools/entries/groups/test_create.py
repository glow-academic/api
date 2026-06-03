"""Tests for create_group."""

import pytest

from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


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
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await create_group_name(conn, redis_client, result.id, "test-group", session.id)
    await refresh_groups(conn)

    # ``name`` is sourced from group_names_entry via the MV/refresh path;
    # the groups write-back cache row holds name="" at create-time by
    # design, so bypass the cache to read the materialized name.
    items = await get_groups(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].name == "test-group"


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, mcp=True, artifact_type="persona")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].mcp is True
