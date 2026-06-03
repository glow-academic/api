"""Tests for search_attempt_message_trees."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message_tree.create import (
    create_attempt_message_tree,
)
from app.tools.entries.attempt_message_tree.refresh import (
    refresh_attempt_message_tree,
)
from app.tools.entries.attempt_message_tree.search import (
    search_attempt_message_trees,
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
        redis_client, session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    real_chat = await create_chat(conn, redis_client, session_id=session.id)
    chat = await create_attempt_chat(
        conn, redis_client, session_id=session.id, chat_id=real_chat.id
    )
    parent_message = await create_attempt_message(
        conn, redis_client, chat_id=chat.id, session_id=session.id
    )
    child_message = await create_attempt_message(
        conn, redis_client, chat_id=chat.id, session_id=session.id
    )
    result = await create_attempt_message_tree(
        conn, redis_client, parent_id=parent_message.id, child_id=child_message.id, session_id=session.id
    )
    return result, parent_message, child_message


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, parent_message, child_message = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, redis_client, message_ids=[child_message.id])

    message_ids = [item.message_id for item in items]
    assert child_message.id in message_ids


async def test_filters_by_message_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, redis_client, message_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, redis_client, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, parent_message, child_message = await _setup(conn, redis_client, profile_id)

    items = await search_attempt_message_trees(
        conn, redis_client, message_ids=[child_message.id], bypass_mv=True
    )

    message_ids = [item.message_id for item in items]
    assert child_message.id in message_ids
