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
    await create_attempt(
        conn,
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    real_chat = await create_chat(conn, session_id=session.id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    chat = await create_attempt_chat(
        conn, call_id=call2.id, group_id=group.id, chat_id=real_chat.id
    )
    msg1 = await create_message(conn, run_id=run.id, role="user")
    msg2 = await create_message(conn, run_id=run.id, role="assistant")
    await create_attempt_message(
        conn, chat_id=chat.id, call_id=call2.id, message_id=msg1.id
    )
    await create_attempt_message(
        conn, chat_id=chat.id, call_id=call2.id, message_id=msg2.id
    )
    result = await create_attempt_message_tree(
        conn, parent_id=msg1.id, child_id=msg2.id, session_id=session.id
    )
    return result, msg1, msg2


async def test_finds_created_entry(conn, profile_id):
    result, msg1, msg2 = await _setup(conn, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, message_ids=[msg2.id])

    message_ids = [item.message_id for item in items]
    assert msg2.id in message_ids


async def test_filters_by_message_id(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, message_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await refresh_attempt_message_tree(conn)

    items = await search_attempt_message_trees(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    result, msg1, msg2 = await _setup(conn, profile_id)

    items = await search_attempt_message_trees(
        conn, message_ids=[msg2.id], bypass_mv=True
    )

    message_ids = [item.message_id for item in items]
    assert msg2.id in message_ids
