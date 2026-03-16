"""Tests for get_groups."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_returns_group_by_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id)
    await refresh_groups(conn)

    items = await get_groups(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, profile_id):
    session = await _session(conn, profile_id)
    r1 = await create_group(conn, session_id=session.id)
    r2 = await create_group(conn, session_id=session.id)
    await refresh_groups(conn)

    items = await get_groups(conn, [r1.id, r2.id])

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, profile_id):
    items = await get_groups(conn, [nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, profile_id):
    items = await get_groups(conn, [])

    assert items == []


async def test_bypass_mv_returns_without_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_group(conn, session_id=session.id)

    items = await get_groups(conn, [result.id], bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
