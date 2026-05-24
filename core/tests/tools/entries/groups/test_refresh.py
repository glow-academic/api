"""Tests for refresh_groups."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_new_group_appears_after_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_group_not_visible_before_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")

    items = await get_groups(conn, [result.id], redis_client)

    assert items == []
