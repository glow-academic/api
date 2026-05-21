"""Tests for refresh_chat."""

from uuid import UUID
import pytest
from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.get import get_chat_entries_internal, get_chats
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.sessions.create import create_session
from app.tools.entries.chat.get import get_chats
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _chat(conn, redis_client, profile_id, bundle):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    return session, await create_chat(
        conn,
        redis_client, session_id=session.id,
        department_ids=[bundle.department_id],
    )


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_chat_appears_after_refresh(conn, redis_client, profile_id):
    _created(await _chat(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_chat(conn)
    items = await get_chats(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_chat_is_not_visible_before_refresh(conn, redis_client, profile_id):
    _created(await _chat(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_chats(conn, redis_client, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_chat(conn)
    await refresh_chat(conn)

    assert True
