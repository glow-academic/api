"""Tests for search_attempt_conversation_completions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_conversation_completion.create import (
    create_attempt_conversation_completion,
)
from app.tools.entries.attempt_conversation_completion.refresh import (
    refresh_attempt_conversation_completion,
)
from app.tools.entries.attempt_conversation_completion.search import (
    search_attempt_conversation_completions,
)
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
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
    conversation = await create_attempt_conversations(
        conn, redis_client, chat_id=attempt_chat.id, call_id=call2.id
    )
    result = await create_attempt_conversation_completion(
        conn,
        redis_client, conversation_id=conversation.id,
        call_id=call2.id,
        stop=False,
        error=False,
        message="",
    )
    return result, conversation


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, conversation = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_conversation_completion(conn)

    items = await search_attempt_conversation_completions(
        conn, redis_client, conversation_ids=[conversation.id]
    )

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_conversation_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_conversation_completion(conn)

    items = await search_attempt_conversation_completions(
        conn, redis_client, conversation_ids=[nonexistent_id()]
    )

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, conversation = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_conversation_completion(conn)

    items = await search_attempt_conversation_completions(
        conn, redis_client, conversation_ids=[conversation.id], limit=1
    )

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_conversation_completion(conn)

    items = await search_attempt_conversation_completions(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, conversation = await _setup(conn, redis_client, profile_id)

    items = await search_attempt_conversation_completions(
        conn, redis_client, conversation_ids=[conversation.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert result.id in ids
