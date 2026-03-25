"""Tests for create_chat."""

from uuid import UUID

import pytest

from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.get import get_chat_entries_internal, get_chats
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _chat(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    return session, await create_chat(
        conn,
        session_id=session.id,
        department_ids=[bundle.department_id],
    )


async def test_returns_id(conn, profile_id, simulation_bundle):
    _, result = await _chat(conn, profile_id, simulation_bundle)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, simulation_bundle):
    _, result = await _chat(conn, profile_id, simulation_bundle)
    await refresh_chat(conn)

    items = await get_chats(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id


async def test_departments_populated(conn, profile_id, simulation_bundle):
    _, result = await _chat(conn, profile_id, simulation_bundle)
    await refresh_chat(conn)

    items = await get_chats(conn, [result.id])

    assert len(items) == 1
    assert simulation_bundle.department_id in items[0].department_ids


async def test_passes_mcp_flag(conn, profile_id, simulation_bundle):
    session = await create_session(conn, profile_id=profile_id)
    result = await create_chat(
        conn,
        session_id=session.id,
        mcp=True,
    )

    row = await conn.fetchrow(
        "SELECT mcp FROM chat_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True


async def test_internal_get_returns_created_chat(conn, profile_id, simulation_bundle):
    _, result = await _chat(conn, profile_id, simulation_bundle)
    await refresh_chat(conn)

    items = await get_chat_entries_internal(conn, [result.id], bypass_cache=True)

    assert len(items) == 1
    assert items[0]["chat_entry_id"] == str(result.id)
    assert simulation_bundle.department_id in {
        UUID(item_id) for item_id in items[0]["department_ids"]
    }
