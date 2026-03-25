"""Tests for search_attempt_contents."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_content.create import create_attempt_content
from app.tools.entries.attempt_content.refresh import refresh_attempt_content
from app.tools.entries.attempt_content.search import search_attempt_contents
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    """Create full chain: session -> ... -> attempt_content."""
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    attempt = await create_attempt(
        conn,
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, session_id=session.id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, call_id=call2.id, group_id=group.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    msg = await create_message(conn, run_id=run.id, role="user")
    call3 = await create_call(conn, run_id=run.id, session_id=session.id)
    await create_attempt_message(
        conn, chat_id=attempt_chat.id, message_id=msg.id, call_id=call3.id
    )
    content_persona = await create_persona(conn)
    result = await create_attempt_content(
        conn,
        message_id=msg.id,
        call_id=call3.id,
        content="Test content",
        persona_id=content_persona.id,
    )
    return result, msg


async def test_finds_created_entry(conn, profile_id):
    result, msg = await _setup(conn, profile_id)
    await refresh_attempt_content(conn)

    items = await search_attempt_contents(conn, message_ids=[msg.id])

    ids = [item.content_id for item in items]
    assert result.id in ids


async def test_filters_by_message_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_content(conn)

    items = await search_attempt_contents(conn, message_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    result, msg = await _setup(conn, profile_id)
    await refresh_attempt_content(conn)

    items = await search_attempt_contents(conn, message_ids=[msg.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_content(conn)

    items = await search_attempt_contents(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, msg = await _setup(conn, profile_id)

    items = await search_attempt_contents(conn, message_ids=[msg.id], bypass_mv=True)

    ids = [item.content_id for item in items]
    assert result.id in ids
