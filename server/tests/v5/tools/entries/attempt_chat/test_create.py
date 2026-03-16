"""Tests for create_attempt_chat."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _attempt_chat(conn, profile_id, **overrides):
    """Create full chain: session → group → run → call → persona → attempt → chat → attempt_chat → bridge."""
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
    defaults = dict(call_id=call2.id, group_id=group.id, chat_id=chat.id)
    defaults.update(overrides)
    result = await create_attempt_chat(conn, **defaults)
    # Bridge is required for MV visibility
    await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt.id,
        attempt_chat_id=result.id,
        session_id=session.id,
    )
    return result, attempt


async def test_returns_id(conn, profile_id):
    result, _ = await _attempt_chat(conn, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    result, attempt = await _attempt_chat(conn, profile_id)
    await refresh_attempt_chat(conn)

    items = await get_attempt_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].chat_id == result.id
    assert items[0].attempt_id == attempt.id


async def test_connections_populated(conn, profile_id):
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
    result = await create_attempt_chat(
        conn,
        call_id=call2.id,
        group_id=group.id,
        chat_id=chat.id,
        title="Test Chat",
        text_enabled=True,
        audio_enabled=True,
    )

    row = await conn.fetchrow(
        "SELECT title, text_enabled, audio_enabled FROM attempt_chat_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["title"] == "Test Chat"
    assert row["text_enabled"] is True
    assert row["audio_enabled"] is True


async def test_passes_mcp_flag(conn, profile_id):
    result, _ = await _attempt_chat(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_chat_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
