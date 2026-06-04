"""Tests for get_attempt_chats."""

import pytest

from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from tests.helpers import create_attempt_chat_graph, nonexistent_id

pytestmark = pytest.mark.asyncio


async def test_gets_created_attempt_chat(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)
    # attempt_chat_mv keys by ``c.id AS chat_id`` where c = attempt_chat_entry,
    # so look up by the attempt_chat_entry id (matching MV / search / prod).
    lookup_id = graph.attempt_chat_id
    items = await get_attempt_chats(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].chat_id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_attempt_chats(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_attempt_chats(conn, ids=[], redis=redis_client)

    assert items == []
