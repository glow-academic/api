"""Tests for refresh_attempt_message_completion."""

import pytest

from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message_completion.create import create_attempt_message_completion
from app.tools.entries.attempt_message_completion.refresh import refresh_attempt_message_completion
from app.tools.entries.attempt_message_completion.refresh import MV_NAME
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup_entry(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(conn, redis_client, session_id=session.id, chat_id=chat.id)
    message = await create_message(conn, redis_client, run_id=run.id, role="user")
    seed = await create_attempt_message(conn, redis_client, chat_id=attempt_chat.id, message_id=message.id, call_id=call.id)
    return session, call, seed


async def test_refresh_is_idempotent(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, call_id=call.id)

    await refresh_attempt_message_completion(conn)

    assert True


async def test_row_not_visible_before_refresh(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, call_id=call.id)

    row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is None


async def test_refresh_exposes_created_row(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_message_completion(conn, redis_client, attempt_message_id=seed.id, session_id=session.id, mcp=True)
    await refresh_attempt_message_completion(conn)

    row = await conn.fetchrow(f"SELECT id, mcp FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is not None
    assert row['id'] == result.id
    assert row['mcp'] is True
