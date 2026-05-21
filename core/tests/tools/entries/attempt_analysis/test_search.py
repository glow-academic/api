"""Tests for search_attempt_analyses."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_analysis.refresh import (
    refresh_attempt_analysis,
)
from app.tools.entries.attempt_analysis.search import search_attempt_analyses
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    await create_attempt(
        conn, redis_client, call_id=call.id, user_persona_id=persona.id, profiles_id=profile_id
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    call2 = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis_client, call_id=call2.id, chat_id=chat.id
    )
    grade = await create_attempt_grade(
        conn,
        redis_client, chat_id=attempt_chat.id,
        call_id=call2.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    result = await create_attempt_analysis(
        conn, redis_client, grade_id=grade.id, call_id=call2.id, content="Test analysis"
    )
    return result, grade


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, grade = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_analysis(conn)

    items = await search_attempt_analyses(conn, redis_client, grade_ids=[grade.id])

    ids = [item.analysis_id for item in items]
    assert result.id in ids


async def test_filters_by_grade_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_analysis(conn)

    items = await search_attempt_analyses(conn, redis_client, grade_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, grade = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_analysis(conn)

    items = await search_attempt_analyses(conn, redis_client, grade_ids=[grade.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_analysis(conn)

    items = await search_attempt_analyses(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, grade = await _setup(conn, redis_client, profile_id)

    items = await search_attempt_analyses(conn, redis_client, grade_ids=[grade.id], bypass_mv=True)

    ids = [item.analysis_id for item in items]
    assert result.id in ids
