"""Tests for search_attempt_strengths."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_strength.create import create_attempt_strength
from app.tools.entries.attempt_strength.refresh import (
    refresh_attempt_strength,
)
from app.tools.entries.attempt_strength.search import search_attempt_strengths
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
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
        conn, call_id=call.id, user_persona_id=persona.id, profiles_id=profile_id
    )
    chat = await create_chat(conn, session_id=session.id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, call_id=call2.id, group_id=group.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    msg = await create_message(conn, run_id=run.id, role="user")
    await create_attempt_message(
        conn, chat_id=attempt_chat.id, call_id=call2.id, message_id=msg.id
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
    result = await create_attempt_strength(
        conn,
        grade_id=grade.id,
        message_id=msg.id,
        call_id=call2.id,
        name="Good greeting",
        description="Student greeted well",
    )
    return result, msg, grade


async def test_finds_created_entry(conn, profile_id):
    result, msg, grade = await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn, message_ids=[msg.id])

    ids = [item.strength_id for item in items]
    assert result.id in ids


async def test_filters_by_message_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn, message_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_grade_id(conn, profile_id):
    result, msg, grade = await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn, grade_ids=[grade.id])

    ids = [item.strength_id for item in items]
    assert result.id in ids


async def test_filters_by_grade_id_nonexistent(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn, grade_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    result, msg, grade = await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn, message_ids=[msg.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_strength(conn)

    items = await search_attempt_strengths(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, msg, grade = await _setup(conn, profile_id)

    items = await search_attempt_strengths(conn, message_ids=[msg.id], bypass_mv=True)

    ids = [item.strength_id for item in items]
    assert result.id in ids
