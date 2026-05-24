"""Tests for search_attempt_message_completions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message_completion.create import create_attempt_message_completion
from app.tools.entries.attempt_message_completion.refresh import refresh_attempt_message_completion
from app.tools.entries.attempt_message_completion.search import search_attempt_message_completions
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(conn, redis_client, session_id=session.id, chat_id=chat.id)
    message = await create_message(conn, redis_client, run_id=run.id, role="user")
    attempt_message = await create_attempt_message(conn, redis_client, chat_id=attempt_chat.id, message_id=message.id, call_id=call.id)
    completion = await create_attempt_message_completion(
        conn, redis_client, attempt_message_id=attempt_message.id, call_id=call.id
    )
    return attempt_message, completion


async def test_finds_created_entry_after_refresh(conn, redis_client, profile_id):
    attempt_message, completion = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_message_completion(conn)

    items = await search_attempt_message_completions(
        conn, redis_client, attempt_message_ids=[attempt_message.id]
    )

    assert any(item.id == completion.id for item in items)


async def test_returns_empty_for_unknown_attempt_message(conn, redis_client):
    items = await search_attempt_message_completions(
        conn, redis_client, attempt_message_ids=[nonexistent_id()], bypass_mv=True
    )

    assert items == []


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    attempt_message, completion = await _setup(conn, redis_client, profile_id)

    items = await search_attempt_message_completions(
        conn, redis_client, attempt_message_ids=[attempt_message.id], bypass_mv=True
    )

    assert any(item.id == completion.id for item in items)
