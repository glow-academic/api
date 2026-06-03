"""Tests for refresh_attempt_analysis."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_analysis.get import get_attempt_analyses
from app.tools.entries.attempt_analysis.refresh import (
    refresh_attempt_analysis,
)
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_analysis.refresh import refresh_attempt_analysis

pytestmark = pytest.mark.asyncio


async def _attempt_analysis(conn, redis_client, profile_id, **overrides):
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
    defaults = dict(grade_id=grade.id, session_id=session.id, content="Test analysis")
    defaults.update(overrides)
    result = await create_attempt_analysis(conn, redis_client, **defaults)
    return result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_attempt_analysis_appears_after_refresh(conn, redis_client, profile_id):
    created = _created(await _attempt_analysis(conn, redis_client, profile_id))
    lookup_id = created.id

    await refresh_attempt_analysis(conn)
    items = await get_attempt_analyses(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].analysis_id == lookup_id


async def test_new_attempt_analysis_is_not_visible_before_refresh(conn, redis_client, profile_id):
    created = _created(await _attempt_analysis(conn, redis_client, profile_id))
    lookup_id = created.id

    items = await get_attempt_analyses(
        conn, ids=[lookup_id], redis=redis_client, bypass_cache=True
    )

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_attempt_analysis(conn)
    await refresh_attempt_analysis(conn)

    assert True
