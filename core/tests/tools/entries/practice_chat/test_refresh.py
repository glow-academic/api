"""Tests for refresh_practice_chat."""

import pytest
from app.tools.entries.chat.create import create_chat
from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice_chat.create import create_practice_chat
from app.tools.entries.practice_chat.get import get_practice_chats
from app.tools.entries.practice_chat.refresh import refresh_practice_chat
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _practice_chat(conn, redis_client, profile_id, bundle):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    practice = await create_practice(
        conn,
        redis_client, session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    practice_chat = await create_practice_chat(
        conn,
        redis_client, practice_id=practice.id,
        chat_id=chat.id,
        session_id=session.id,
    )
    return session, practice, chat, practice_chat


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_practice_chat_appears_after_refresh(conn, redis_client, profile_id):
    _created(await _practice_chat(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_practice_chat(conn)
    items = await get_practice_chats(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_practice_chat_is_not_visible_before_refresh(conn, redis_client, profile_id):
    _created(await _practice_chat(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_practice_chats(conn, redis_client, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_practice_chat(conn)
    await refresh_practice_chat(conn)

    assert True
