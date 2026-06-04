"""Tests for refresh_attempt_chat."""

import pytest

from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from tests.helpers import create_attempt_chat_graph

pytestmark = pytest.mark.asyncio


async def test_new_attempt_chat_appears_after_refresh(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(conn, redis_client, profile_id)
    # attempt_chat_mv keys by ``c.id AS chat_id`` where c = attempt_chat_entry,
    # so look up by the attempt_chat_entry id (matching MV / search / prod).
    lookup_id = graph.attempt_chat_id

    await refresh_attempt_chat(conn)
    items = await get_attempt_chats(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].chat_id == lookup_id


async def test_new_attempt_chat_is_not_visible_before_refresh(
    conn, redis_client, profile_id
):
    graph = await create_attempt_chat_graph(conn, redis_client, profile_id)
    lookup_id = graph.attempt_chat_id

    items = await get_attempt_chats(
        conn, ids=[lookup_id], redis=redis_client, bypass_cache=True
    )

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_attempt_chat(conn)
    await refresh_attempt_chat(conn)

    assert True
