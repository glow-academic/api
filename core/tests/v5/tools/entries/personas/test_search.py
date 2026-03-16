"""Tests for search_personas."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.search import search_personas
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_search_finds_created(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_personas(conn, session_id=session.id)

    items = await search_personas(conn, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_filters_by_session(conn, profile_id):
    session = await _session(conn, profile_id)
    await create_personas(conn, session_id=session.id)

    items = await search_personas(conn, session_ids=[nonexistent_id()])

    assert items == []


async def test_search_returns_connections(conn, profile_id):
    session = await _session(conn, profile_id)
    persona_id = await conn.fetchval("SELECT id FROM personas_resource LIMIT 1")
    assert persona_id is not None, (
        "Need at least one personas_resource row as seed data"
    )

    result = await create_personas(
        conn, session_id=session.id, persona_ids=[persona_id]
    )

    items = await search_personas(conn, session_ids=[session.id])

    matched = [item for item in items if item.id == result.id]
    assert len(matched) == 1
    assert persona_id in matched[0].persona_ids


async def test_search_pagination(conn, profile_id):
    session = await _session(conn, profile_id)
    await create_personas(conn, session_id=session.id)
    await create_personas(conn, session_id=session.id)

    items = await search_personas(conn, session_ids=[session.id], limit=1)

    assert len(items) == 1
