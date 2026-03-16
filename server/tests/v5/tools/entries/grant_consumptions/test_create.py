"""Tests for create_grant_consumption."""

import pytest

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


async def test_returns_id(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)

    assert result.id is not None


async def test_visible_via_get(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].grant_id == grant.id
    assert items[0].active is True
    assert items[0].mcp is False
    assert items[0].generated is True


async def test_passes_mcp_flag(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id, mcp=True)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True
