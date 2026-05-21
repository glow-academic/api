"""Tests for get_personas."""

import pytest
from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_personas(conn, redis_client):
    created = _created(await create_personas(conn, redis_client))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_personas(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_personas(conn, redis_client, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_personas(conn, redis_client, ids=[])

    assert items == []
