"""Tests for search_chat_entries_internal."""

from uuid import UUID
import pytest
from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.get import get_chat_entries_internal, get_chats
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.sessions.create import create_session
from app.tools.entries.chat.get import get_chats
from app.tools.entries.chat.search import search_chat_entries_internal
from tests.helpers import nonexistent_id, unique_tag

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


async def test_finds_created_chat(conn, redis_client, profile_id):
    _created(await _chat(conn, redis_client, profile_id))
    await refresh_chat(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    fetched = await get_chats(conn, ids=[lookup_id], redis=redis_client)
    row = fetched[0]
    filter_value = getattr(row, 'parent_id', None)
    items = await search_chat_entries_internal(conn, redis_client, parent_ids=[filter_value], limit_count=20, offset_count=0)

    assert len(items) >= 1
    assert any(item['id'] == lookup_id for item in items)


async def test_returns_empty_for_unmatched_filter(conn, redis_client, profile_id):
    _created(await _chat(conn, redis_client, profile_id))
    await refresh_chat(conn)
    items = await search_chat_entries_internal(conn, redis_client, parent_ids=[nonexistent_id()], limit_count=20, offset_count=0)

    assert items == []


async def test_respects_limit(conn, redis_client, profile_id):
    _created(await _chat(conn, redis_client, profile_id))
    await refresh_chat(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    fetched = await get_chats(conn, ids=[lookup_id], redis=redis_client)
    row = fetched[0]
    filter_value = getattr(row, 'parent_id', None)
    items = await search_chat_entries_internal(conn, redis_client, parent_ids=[filter_value], limit_count=1, offset_count=0)

    assert len(items) <= 1
