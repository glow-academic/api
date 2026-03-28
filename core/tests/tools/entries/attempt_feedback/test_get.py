"""Tests for get_attempt_feedbacks."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_feedback.create import create_attempt_feedback
from app.tools.entries.attempt_feedback.get import get_attempt_feedbacks
from app.tools.entries.attempt_feedback.refresh import (
    refresh_attempt_feedback,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_feedback.refresh import refresh_attempt_feedback
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_feedback(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    await create_attempt(
        conn, call_id=call.id, user_persona_id=persona.id, profiles_id=profile_id
    )
    chat = await create_chat(conn, session_id=session.id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, call_id=call2.id, group_id=group.id, chat_id=chat.id
    )
    grade = await create_attempt_grade(
        conn,
        chat_id=attempt_chat.id,
        call_id=call2.id,
        run_id=run.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    defaults = dict(grade_id=grade.id, call_id=call2.id, total=10, feedback="Good job")
    defaults.update(overrides)
    result = await create_attempt_feedback(conn, **defaults)
    return result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt_feedback(conn, profile_id):
    _created(await _attempt_feedback(conn, profile_id))
    await refresh_attempt_feedback(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_attempt_feedbacks(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_attempt_feedbacks(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_attempt_feedbacks(conn, ids=[])

    assert items == []
