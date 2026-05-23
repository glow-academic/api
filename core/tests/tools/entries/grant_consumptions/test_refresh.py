"""Tests for refresh_grant_consumptions."""

import pytest

from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grant_consumptions.get import (
    get_grant_consumptions,
)
from app.tools.entries.grant_consumptions.refresh import (
    refresh_grant_consumptions,
)
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    grant = await create_grant(conn, redis_client, session_id=session.id)
    return await create_grant_consumption(conn, redis_client, grant_id=grant.id)


async def test_appears_after_refresh(conn, redis_client, profile_id):
    result = await _setup(conn, redis_client, profile_id)
    await refresh_grant_consumptions(conn)

    items = await get_grant_consumptions(conn, ids=[result.id], redis=redis_client)
    assert len(items) >= 1


async def test_not_visible_before_refresh(conn, redis_client, profile_id):
    result = await _setup(conn, redis_client, profile_id)

    items = await get_grant_consumptions(conn, ids=[result.id], redis=redis_client)
    assert len(items) == 0
