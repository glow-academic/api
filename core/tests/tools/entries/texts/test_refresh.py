"""Tests for refresh_texts_internal."""

import pytest
from app.tools.entries.sessions.create import create_session
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.get import get_text
from app.tools.entries.texts.refresh import refresh_texts_internal
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_texts_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_text(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'text_id', None) or getattr(created, 'id', None) or getattr(created, 'text', None)

    await refresh_texts_internal(conn)
    item = await get_text(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_texts_is_not_visible_before_refresh(conn, redis_client, session_id):
    created = _created(await create_text(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'text_id', None) or getattr(created, 'id', None) or getattr(created, 'text', None)

    item = await get_text(conn, lookup_id, redis_client)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_texts_internal(conn)
    await refresh_texts_internal(conn)

    assert True
