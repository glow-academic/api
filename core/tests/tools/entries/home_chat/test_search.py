"""Tests for search_home_chats."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.chat.create import create_chat
from app.tools.entries.home.create import create_home
from app.tools.entries.home_chat.create import create_home_chat
from app.tools.entries.home_chat.refresh import refresh_home_chat
from app.tools.entries.home_chat.search import search_home_chats
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, bundle):
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
    return home, chat, home_chat


async def test_finds_created_entry(conn, profile_id, simulation_bundle):
    home, chat, result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await search_home_chats(conn, home_ids=[home.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_home_id(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await search_home_chats(conn, home_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_chat_id(conn, profile_id, simulation_bundle):
    home, chat, result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await search_home_chats(conn, chat_ids=[chat.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, profile_id, simulation_bundle):
    home, _, _ = await _setup(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await search_home_chats(conn, home_ids=[home.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_home_chat(conn)

    items = await search_home_chats(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, simulation_bundle):
    home, _, result = await _setup(conn, profile_id, simulation_bundle)

    items = await search_home_chats(conn, home_ids=[home.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
