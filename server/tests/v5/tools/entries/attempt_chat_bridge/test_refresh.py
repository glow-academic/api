"""Tests for refresh_attempt_chat_bridge."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.get import (
    get_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.refresh import (
    refresh_attempt_chat_bridge,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
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
    return await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )


async def test_appears_after_refresh(conn, profile_id):
    result = await _setup(conn, profile_id)
    await refresh_attempt_chat_bridge(conn)

    items = await get_attempt_chat_bridge(conn, attempt_ids=[result.attempt_id])
    assert len(items) >= 1


async def test_not_visible_before_refresh(conn, profile_id):
    result = await _setup(conn, profile_id)

    items = await get_attempt_chat_bridge(conn, attempt_ids=[result.attempt_id])
    assert len(items) == 0
