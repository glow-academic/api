"""Tests for create_attempt_chat."""

import pytest

from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from tests.helpers import create_attempt_chat_graph

pytestmark = pytest.mark.asyncio


async def test_returns_id(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(conn, redis_client, profile_id)

    assert graph.attempt_chat_id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    # The attempt_chat MV/cache is keyed by the base chat id (chat_id), so
    # reads look the entry up by graph.chat_id, not the attempt_chat_entry id.
    items = await get_attempt_chats(conn, [graph.chat_id], redis_client)

    assert len(items) == 1
    assert items[0].chat_id == graph.chat_id
    assert items[0].attempt_id == graph.attempt_id


async def test_connections_populated(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(
        conn,
        redis_client,
        profile_id,
        title="Test Chat",
        text_enabled=True,
        audio_enabled=True,
    )

    row = await conn.fetchrow(
        "SELECT title, text_enabled, audio_enabled FROM attempt_chat_entry WHERE id = $1",
        graph.attempt_chat_id,
    )
    assert row is not None
    assert row["title"] == "Test Chat"
    assert row["text_enabled"] is True
    assert row["audio_enabled"] is True


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    graph = await create_attempt_chat_graph(
        conn, redis_client, profile_id, mcp=True
    )

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_chat_entry WHERE id = $1",
        graph.attempt_chat_id,
    )
    assert row is not None
    assert row["mcp"] is True
