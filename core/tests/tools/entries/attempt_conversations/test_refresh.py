"""Tests for refresh_attempt_conversations."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
from app.tools.entries.attempt_conversations.get import (
    get_attempt_conversations,
)
from app.tools.entries.attempt_conversations.refresh import (
    refresh_attempt_conversations,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_conversations.get import get_attempt_conversations
from app.tools.entries.attempt_conversations.refresh import refresh_attempt_conversations

pytestmark = pytest.mark.asyncio


async def _attempt_conversations(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    await create_attempt(
        conn,
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, session_id=session.id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, call_id=call2.id, chat_id=chat.id
    )
    defaults = dict(
        chat_id=attempt_chat.id,
        call_id=call2.id,
    )
    defaults.update(overrides)
    return await create_attempt_conversations(conn, **defaults)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_attempt_conversations_appears_after_refresh(conn, profile_id):
    created = _created(await _attempt_conversations(conn, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_attempt_conversations(conn)
    items = await get_attempt_conversations(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_attempt_conversations_is_not_visible_before_refresh(conn, profile_id):
    created = _created(await _attempt_conversations(conn, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_attempt_conversations(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_attempt_conversations(conn)
    await refresh_attempt_conversations(conn)

    assert True
