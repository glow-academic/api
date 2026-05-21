"""Tests for get_home_chats."""

import pytest
from app.tools.entries.chat.create import create_chat
from app.tools.entries.home.create import create_home
from app.tools.entries.home_chat.create import create_home_chat
from app.tools.entries.home_chat.get import get_home_chats
from app.tools.entries.home_chat.refresh import refresh_home_chat
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _home_chat(conn, redis_client, profile_id, bundle):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    home = await create_home(
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
    home_chat = await create_home_chat(
        conn,
        redis_client, home_id=home.id,
        chat_id=chat.id,
        session_id=session.id,
    )
    return session, home, chat, home_chat


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_home_chat(conn, redis_client, profile_id):
    _created(await _home_chat(conn, redis_client, profile_id))
    await refresh_home_chat(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_home_chats(conn, redis_client, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_home_chats(conn, redis_client, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_home_chats(conn, redis_client, ids=[])

    assert items == []
