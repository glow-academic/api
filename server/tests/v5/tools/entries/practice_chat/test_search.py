"""Tests for search_practice_chats."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.chat.create import create_chat
from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice_chat.create import create_practice_chat
from app.tools.entries.practice_chat.refresh import refresh_practice_chat
from app.tools.entries.practice_chat.search import search_practice_chats
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, bundle):
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
    return practice, chat, practice_chat


async def test_finds_created_entry(conn, profile_id, simulation_bundle):
    practice, chat, result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await search_practice_chats(conn, practice_ids=[practice.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_practice_id(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await search_practice_chats(conn, practice_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_chat_id(conn, profile_id, simulation_bundle):
    practice, chat, result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await search_practice_chats(conn, chat_ids=[chat.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, profile_id, simulation_bundle):
    practice, _, _ = await _setup(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await search_practice_chats(conn, practice_ids=[practice.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_practice_chat(conn)

    items = await search_practice_chats(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, simulation_bundle):
    practice, _, result = await _setup(conn, profile_id, simulation_bundle)

    items = await search_practice_chats(
        conn, practice_ids=[practice.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert result.id in ids
