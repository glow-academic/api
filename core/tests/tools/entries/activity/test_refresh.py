"""Tests for refresh_activity."""

import pytest

from app.tools.entries.activity.create import create_activity
from app.tools.entries.activity.get import get_activity
from app.tools.entries.activity.refresh import refresh_activity
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_new_activity_appears_after_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_activity(conn, redis_client, session_id=session.id)
    await refresh_activity(conn)

    items = await get_activity(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_activity_not_visible_before_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_activity(conn, redis_client, session_id=session.id)

    # get_activity's bypass_cache path reads the genuine activity_mv (via
    # resolve_mv_source), which create does not write to — so bypassing the
    # read-back cache correctly hides the new row until refresh.
    items = await get_activity(conn, [result.id], redis_client, bypass_cache=True)

    assert items == []
