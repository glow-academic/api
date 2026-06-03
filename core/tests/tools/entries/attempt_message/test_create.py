"""Tests for create_attempt_message."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_content.create import create_attempt_content
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message.get import get_attempt_messages
from app.tools.entries.attempt_message.refresh import refresh_attempt_message
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _attempt_message(conn, redis_client, profile_id, **overrides):
    """Create full chain: session → ... → attempt → attempt_chat → bridge → message → attempt_message."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis_client, session_id=session.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        redis_client, attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    defaults = dict(chat_id=attempt_chat.id, session_id=session.id)
    defaults.update(overrides)
    result = await create_attempt_message(conn, redis_client, **defaults)
    # A message is a "query" (vs "response") when its first content is authored
    # by the attempt's user persona — see attempt_message_mv.message_type.
    await create_attempt_content(
        conn,
        redis_client,
        message_id=result.id,
        session_id=session.id,
        content="hello",
        persona_id=persona.id,
    )
    return result, attempt_chat


async def test_returns_id(conn, redis_client, profile_id):
    result, _ = await _attempt_message(conn, redis_client, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    result, attempt_chat = await _attempt_message(conn, redis_client, profile_id)
    await refresh_attempt_message(conn)

    items = await get_attempt_messages(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].message_id == result.id
    assert items[0].chat_id == attempt_chat.id


async def test_message_type_is_query(conn, redis_client, profile_id):
    """User messages show as 'query' type in the MV."""
    result, _ = await _attempt_message(conn, redis_client, profile_id)
    await refresh_attempt_message(conn)

    # ``type`` is derived by the MV (not stored in the write-back cache, which
    # carries type=None), so bypass the cache to read the MV-computed value.
    items = await get_attempt_messages(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].type == "query"


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    result, _ = await _attempt_message(conn, redis_client, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_message_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
