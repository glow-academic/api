"""Tests for get_chats."""

from uuid import UUID
import pytest
from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.get import get_chat_entries_internal, get_chats
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.sessions.create import create_session
from app.tools.entries.chat.get import get_chats
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _chat(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    return session, await create_chat(
        conn,
        session_id=session.id,
        department_ids=[bundle.department_id],
    )


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_chat(conn, profile_id):
    _created(await _chat(conn, profile_id))
    await refresh_chat(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_chats(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_chats(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_chats(conn, ids=[])

    assert items == []
