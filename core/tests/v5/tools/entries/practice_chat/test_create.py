"""Tests for create_practice_chat."""

import pytest

from app.tools.entries.chat.create import create_chat
from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice_chat.create import create_practice_chat
from app.tools.entries.practice_chat.get import get_practice_chats
from app.tools.entries.practice_chat.refresh import refresh_practice_chat
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _practice_chat(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    practice = await create_practice(
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
    practice_chat = await create_practice_chat(
        conn,
        practice_id=practice.id,
        chat_id=chat.id,
        session_id=session.id,
    )
    return session, practice, chat, practice_chat


async def test_returns_id(conn, profile_id, simulation_bundle):
    _, _, _, result = await _practice_chat(conn, profile_id, simulation_bundle)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, simulation_bundle):
    _, _, _, result = await _practice_chat(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await get_practice_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].active is True


async def test_links_practice_and_chat(conn, profile_id, simulation_bundle):
    _, practice, chat, result = await _practice_chat(
        conn, profile_id, simulation_bundle
    )
    await refresh_practice_chat(conn)

    items = await get_practice_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].practice_id == practice.id
    assert items[0].chat_id == chat.id


async def test_passes_mcp_flag(conn, profile_id, simulation_bundle):
    bundle = simulation_bundle
    session = await create_session(conn, profile_id=profile_id)
    practice = await create_practice(
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
    result = await create_practice_chat(
        conn,
        practice_id=practice.id,
        chat_id=chat.id,
        session_id=session.id,
        mcp=True,
    )

    row = await conn.fetchrow(
        "SELECT mcp FROM practice_chat_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
