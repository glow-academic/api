"""Tests for search_personas."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.persona.create import create_persona
from app.tools.entries.persona.refresh import refresh_persona_internal
from app.tools.entries.persona.search import search_personas
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def test_finds_created_entry(conn):
    result = await create_persona(conn)
    await refresh_persona_internal(conn)

    items = await search_personas(conn)

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session_id(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    await conn.execute(
        "INSERT INTO personas_entry (session_id, generated) VALUES ($1, true)",
        session.id,
    )
    await refresh_persona_internal(conn)

    items = await search_personas(conn, session_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn):
    await create_persona(conn)
    await create_persona(conn)
    await refresh_persona_internal(conn)

    items = await search_personas(conn, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn):
    await create_persona(conn)
    await refresh_persona_internal(conn)

    items = await search_personas(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn):
    result = await create_persona(conn)

    items = await search_personas(conn, bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
