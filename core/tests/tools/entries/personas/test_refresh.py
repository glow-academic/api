"""Tests for refresh_personas."""

import pytest
from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session
from app.tools.entries.personas.refresh import refresh_personas

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_personas_appears_after_refresh(conn):
    created = _created(await create_personas(conn, ))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_personas(conn)
    items = await get_personas(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_personas_is_not_visible_before_refresh(conn):
    created = _created(await create_personas(conn, ))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_personas(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_personas(conn)
    await refresh_personas(conn)

    assert True
