"""Tests for search_attempt_chats."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat.search import (
    search_attempt_chats,
)
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.roles.create import create_role
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    """Create full chain: session -> group -> run -> call -> persona -> attempt -> chat -> attempt_chat -> bridge."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    result = await create_attempt_chat(
        conn, redis_client, session_id=session.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        redis_client, attempt_id=attempt.id,
        attempt_chat_id=result.id,
        session_id=session.id,
    )
    return result, attempt, group


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, attempt, _ = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(conn, redis_client, attempt_ids=[attempt.id])

    ids = [item.chat_id for item in items]
    assert result.id in ids


async def test_filters_by_attempt_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(
        conn, redis_client, attempt_ids=[nonexistent_id()]
    )

    assert items == []


async def test_filters_by_role_id(conn, redis_client):
    role = await create_role(conn, redis_client, name=f"attempt-chat-role-{nonexistent_id()}")
    profile = await create_profile(conn, redis_client, role_id=role.id)
    result, _attempt, _group = await _setup(conn, redis_client, profile.id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(conn, redis_client, role_ids=[role.id])

    ids = [item.chat_id for item in items]
    assert result.id in ids


async def test_filters_by_missing_role_id(conn, redis_client):
    role = await create_role(conn, redis_client, name=f"attempt-chat-role-{nonexistent_id()}")
    profile = await create_profile(conn, redis_client, role_id=role.id)
    await _setup(conn, redis_client, profile.id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(conn, redis_client, role_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_group_id(conn, redis_client, profile_id):
    result, _, group = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(conn, redis_client, group_ids=[group.id])

    ids = [item.chat_id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    result, attempt, _ = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(
        conn, redis_client, attempt_ids=[attempt.id], limit=1
    )

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_chat(conn)

    items, _total_count = await search_attempt_chats(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, attempt, _ = await _setup(conn, redis_client, profile_id)

    items, _total_count = await search_attempt_chats(
        conn, redis_client, attempt_ids=[attempt.id], bypass_mv=True
    )

    ids = [item.chat_id for item in items]
    assert result.id in ids
