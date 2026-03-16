"""Tests for create_attempt_chat_bridge."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
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


async def _attempt_chat_bridge(conn, profile_id, **overrides):
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
    defaults = dict(
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    defaults.update(overrides)
    result = await create_attempt_chat_bridge(conn, **defaults)
    return result, attempt, attempt_chat


async def test_returns_ids(conn, profile_id):
    result, attempt, attempt_chat = await _attempt_chat_bridge(conn, profile_id)

    assert result.attempt_id == attempt.id
    assert result.attempt_chat_id == attempt_chat.id


async def test_row_exists(conn, profile_id):
    result, _, _ = await _attempt_chat_bridge(conn, profile_id)

    row = await conn.fetchrow(
        "SELECT attempt_id, attempt_chat_id FROM attempt_chat_bridge_entry WHERE attempt_id = $1 AND attempt_chat_id = $2",
        result.attempt_id,
        result.attempt_chat_id,
    )
    assert row is not None


async def test_passes_mcp_flag(conn, profile_id):
    result, _, _ = await _attempt_chat_bridge(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_chat_bridge_entry WHERE attempt_id = $1",
        result.attempt_id,
    )
    assert row is not None
    assert row["mcp"] is True
