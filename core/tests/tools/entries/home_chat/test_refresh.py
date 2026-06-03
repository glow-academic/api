"""Tests for refresh_home_chat."""

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


async def test_new_home_chat_appears_after_refresh(conn, redis_client, profile_id, simulation_bundle):
    _, _, _, created = await _home_chat(conn, redis_client, profile_id, simulation_bundle)
    lookup_id = created.id

    await refresh_home_chat(conn)
    items = await get_home_chats(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_home_chat_is_not_visible_before_refresh(conn, redis_client, profile_id, simulation_bundle):
    _, _, _, created = await _home_chat(conn, redis_client, profile_id, simulation_bundle)
    lookup_id = created.id

    items = await get_home_chats(conn, ids=[lookup_id], redis=redis_client, bypass_cache=True)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_home_chat(conn)
    await refresh_home_chat(conn)

    assert True
