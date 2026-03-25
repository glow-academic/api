"""Tests for create_home_chat."""

import pytest

from app.tools.entries.chat.create import create_chat
from app.tools.entries.home.create import create_home
from app.tools.entries.home_chat.create import create_home_chat
from app.tools.entries.home_chat.get import get_home_chats
from app.tools.entries.home_chat.refresh import refresh_home_chat
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _home_chat(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    home = await create_home(
        conn,
        session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
    )
    chat = await create_chat(conn, session_id=session.id)
    home_chat = await create_home_chat(
        conn,
        home_id=home.id,
        chat_id=chat.id,
        session_id=session.id,
    )
    return session, home, chat, home_chat


async def test_returns_id(conn, profile_id, simulation_bundle):
    _, _, _, result = await _home_chat(conn, profile_id, simulation_bundle)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, simulation_bundle):
    _, _, _, result = await _home_chat(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await get_home_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].active is True


async def test_links_home_and_chat(conn, profile_id, simulation_bundle):
    _, home, chat, result = await _home_chat(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await get_home_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].home_id == home.id
    assert items[0].chat_id == chat.id


async def test_passes_mcp_flag(conn, profile_id, simulation_bundle):
    bundle = simulation_bundle
    session = await create_session(conn, profile_id=profile_id)
    home = await create_home(
        conn,
        session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
    )
    chat = await create_chat(conn, session_id=session.id)
    result = await create_home_chat(
        conn,
        home_id=home.id,
        chat_id=chat.id,
        session_id=session.id,
        mcp=True,
    )

    row = await conn.fetchrow(
        "SELECT mcp FROM home_chat_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
