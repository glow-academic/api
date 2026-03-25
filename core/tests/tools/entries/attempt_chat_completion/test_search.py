"""Tests for search_attempt_chat_completions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)
from app.tools.entries.attempt_chat_completion.refresh import (
    refresh_attempt_chat_completion,
)
from app.tools.entries.attempt_chat_completion.search import (
    search_attempt_chat_completions,
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
    await create_attempt(
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
    result = await create_attempt_chat_completion(
        conn,
        chat_id=attempt_chat.id,
        call_id=call2.id,
        stop=False,
        error=False,
        message="",
    )
    return result, attempt_chat


async def test_finds_created_entry(conn, profile_id):
    result, attempt_chat = await _setup(conn, profile_id)
    await refresh_attempt_chat_completion(conn)

    items = await search_attempt_chat_completions(conn, chat_ids=[attempt_chat.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_chat_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_chat_completion(conn)

    items = await search_attempt_chat_completions(conn, chat_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    result, attempt_chat = await _setup(conn, profile_id)
    await refresh_attempt_chat_completion(conn)

    items = await search_attempt_chat_completions(
        conn, chat_ids=[attempt_chat.id], limit=1
    )

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_chat_completion(conn)

    items = await search_attempt_chat_completions(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, attempt_chat = await _setup(conn, profile_id)

    items = await search_attempt_chat_completions(
        conn, chat_ids=[attempt_chat.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert result.id in ids
