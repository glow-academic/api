"""Tests for get_grant_consumptions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grant_consumptions.get import get_grant_consumptions
from app.tools.entries.grant_consumptions.refresh import (
    refresh_grant_consumptions,
)
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _grant(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    grant = await create_grant(conn, session_id=session.id)
    return grant


async def test_returns_by_id(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].grant_id == grant.id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, profile_id):
    grant = await _grant(conn, profile_id)
    r1 = await create_grant_consumption(conn, grant_id=grant.id)
    r2 = await create_grant_consumption(conn, grant_id=grant.id)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [r1.id, r2.id])

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, profile_id):
    items = await get_grant_consumptions(conn, [nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, profile_id):
    items = await get_grant_consumptions(conn, [])

    assert items == []
