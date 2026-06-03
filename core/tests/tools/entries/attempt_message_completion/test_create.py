"""Tests for create_attempt_message_completion."""

import pytest

from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message_completion.create import create_attempt_message_completion
from app.tools.entries.attempt_message_completion.refresh import refresh_attempt_message_completion
from app.tools.entries.attempt_message_completion.refresh import MV_NAME
from app.tools.entries.chat.create import create_chat
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup_entry(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(conn, redis_client, session_id=session.id, chat_id=chat.id)
    seed = await create_attempt_message(conn, redis_client, chat_id=attempt_chat.id, session_id=session.id)
    return session, seed


async def test_create_returns_id(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, session_id=session.id)

    assert result.id is not None


async def test_row_not_visible_before_refresh(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, session_id=session.id)

    row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is None


async def test_refresh_exposes_created_row(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, session_id=session.id, mcp=True)
    await refresh_attempt_message_completion(conn)

    row = await conn.fetchrow(f"SELECT id, mcp FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is not None
    assert row['id'] == result.id
    assert row['mcp'] is True
