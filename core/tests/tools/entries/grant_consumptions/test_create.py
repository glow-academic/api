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


async def _grant(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    grant = await create_grant(conn, redis_client, session_id=session.id)
    return grant


async def test_returns_id(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    assert result.id is not None


async def test_visible_via_get(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].grant_id == grant.id
    assert items[0].active is True
    assert items[0].mcp is False
    assert items[0].generated is True


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id, mcp=True)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].mcp is True


async def test_single_use_second_consume_rejected(conn, redis_client, profile_id):
    """I1: a single-use grant is consumed exactly once — the race-loser is rejected.

    Two consumes of the same grant: the first wins (returns a response), the
    second hits the partial-unique index (ON CONFLICT DO NOTHING) and returns
    None. This is the atomic gate that prevents emulation-grant replay.
    """
    grant = await _grant(conn, redis_client, profile_id)

    first = await create_grant_consumption(conn, redis_client, grant_id=grant.id)
    second = await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    assert first is not None
    assert first.id is not None
    assert second is None  # race-loser denied — grant consumed exactly once


async def test_soft_consume_not_blocked_by_active(conn, redis_client, profile_id):
    """Soft (inactive) consumptions are exempt from the WHERE active predicate."""
    grant = await _grant(conn, redis_client, profile_id)

    active = await create_grant_consumption(conn, redis_client, grant_id=grant.id)
    soft = await create_grant_consumption(conn, redis_client, grant_id=grant.id, soft=True)

    assert active is not None
    assert soft is not None  # inactive row does not conflict with the active one
