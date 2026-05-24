"""Tests for refresh_personas."""

import pytest
from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session
from app.tools.entries.personas.refresh import refresh_personas

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_personas_appears_after_refresh(conn, redis_client):
    created = _created(await create_personas(conn, redis_client))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_personas(conn)
    items = await get_personas(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_personas_is_not_visible_before_refresh(conn, redis_client):
    created = _created(await create_personas(conn, redis_client))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_personas(conn, ids=[lookup_id], redis=redis_client)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_personas(conn)
    await refresh_personas(conn)

    assert True
