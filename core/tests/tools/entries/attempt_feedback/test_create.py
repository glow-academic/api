"""Tests for create_attempt_feedback."""

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

pytestmark = pytest.mark.asyncio


async def _attempt_feedback(conn, redis_client, profile_id, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    await create_attempt(
        conn, redis_client, session_id=session.id, user_persona_id=persona.id, profiles_id=profile_id
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis_client, session_id=session.id, chat_id=chat.id
    )
    grade = await create_attempt_grade(
        conn,
        redis_client, chat_id=attempt_chat.id,
        session_id=session.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    defaults = dict(grade_id=grade.id, session_id=session.id, total=10, feedback="Good job")
    defaults.update(overrides)
    result = await create_attempt_feedback(conn, redis_client, **defaults)
    return result


async def test_returns_id(conn, redis_client, profile_id):
    result = await _attempt_feedback(conn, redis_client, profile_id)
    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    result = await _attempt_feedback(conn, redis_client, profile_id)
    await refresh_attempt_feedback(conn)
    items = await get_attempt_feedbacks(conn, [result.id], redis_client)
    assert len(items) == 1


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    result = await _attempt_feedback(conn, redis_client, profile_id, mcp=True)
    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_feedback_entry WHERE id = $1", result.id
    )
    assert row is not None
    assert row["mcp"] is True
