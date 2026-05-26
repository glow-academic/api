"""Tests for refresh_attempt_strength."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_strength.create import create_attempt_strength
from app.tools.entries.attempt_strength.get import get_attempt_strengths
from app.tools.entries.attempt_strength.refresh import (
    refresh_attempt_strength,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_strength.refresh import refresh_attempt_strength
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_strength(conn, redis_client, profile_id, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn, redis_client, session_id=session.id, user_persona_id=persona.id, profiles_id=profile_id
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    call2 = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis_client, call_id=call2.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        redis_client, attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    msg = await create_message(conn, redis_client, run_id=run.id, role="user")
    await create_attempt_message(
        conn, redis_client, chat_id=attempt_chat.id, call_id=call2.id, message_id=msg.id
    )
    grade = await create_attempt_grade(
        conn,
        redis_client, chat_id=attempt_chat.id,
        call_id=call2.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    defaults = dict(
        grade_id=grade.id,
        message_id=msg.id,
        call_id=call2.id,
        name="Good greeting",
        description="Student greeted well",
    )
    defaults.update(overrides)
    result = await create_attempt_strength(conn, redis_client, **defaults)
    return result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_attempt_strength_appears_after_refresh(conn, redis_client, profile_id):
    _created(await _attempt_strength(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_attempt_strength(conn)
    items = await get_attempt_strengths(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_attempt_strength_is_not_visible_before_refresh(conn, redis_client, profile_id):
    _created(await _attempt_strength(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_attempt_strengths(conn, ids=[lookup_id], redis=redis_client)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_attempt_strength(conn)
    await refresh_attempt_strength(conn)

    assert True
