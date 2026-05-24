"""Tests for get_grants."""

import pytest
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session
from app.tools.entries.grants.get import get_grants
from tests.helpers import nonexistent_id
from app.tools.entries.grants.refresh import refresh_grants_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_grants(conn, redis_client, session_id):
    created = _created(await create_grant(conn, redis_client, session_id=session_id))
    await refresh_grants_internal(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_grants(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_grants(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_grants(conn, ids=[], redis=redis_client)

    assert items == []
