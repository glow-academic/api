"""Tests for get_attempt_grades."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_grade.get import get_attempt_grades
from app.tools.entries.attempt_grade.refresh import refresh_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_grade(conn, redis_client, profile_id, **overrides):
    """Create full chain: session -> group -> run -> call -> attempt -> call2 -> attempt_chat -> attempt_grade."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
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
    defaults = dict(
        chat_id=attempt_chat.id,
        call_id=call2.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    defaults.update(overrides)
    result = await create_attempt_grade(conn, redis_client, **defaults)
    return result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt_grade(conn, redis_client, profile_id):
    _created(await _attempt_grade(conn, redis_client, profile_id))
    await refresh_attempt_grade(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_attempt_grades(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_attempt_grades(conn, redis_client, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_attempt_grades(conn, redis_client, ids=[])

    assert items == []
