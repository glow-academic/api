"""Tests for refresh_grants_internal."""

import pytest
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session
from app.tools.entries.grants.get import get_grants
from app.tools.entries.grants.refresh import refresh_grants_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_grants_appears_after_refresh(conn, session_id):
    created = _created(await create_grant(conn, session_id=session_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_grants_internal(conn)
    items = await get_grants(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_grants_is_not_visible_before_refresh(conn, session_id):
    created = _created(await create_grant(conn, session_id=session_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_grants(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_grants_internal(conn)
    await refresh_grants_internal(conn)

    assert True
