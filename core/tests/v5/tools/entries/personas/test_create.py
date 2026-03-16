"""Tests for create_personas."""

import pytest

from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_create_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_personas(conn, session_id=session.id)

    assert result.id is not None


async def test_roundtrip_base_fields(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_personas(conn, session_id=session.id)

    items = await get_personas(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].generated is True
    assert items[0].mcp is False


async def test_create_without_connections_returns_empty_list(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_personas(conn, session_id=session.id)

    items = await get_personas(conn, [result.id])

    assert len(items) == 1
    assert items[0].persona_ids == []


async def test_create_with_connections(conn, profile_id):
    session = await _session(conn, profile_id)
    persona_id = await conn.fetchval("SELECT id FROM personas_resource LIMIT 1")
    assert persona_id is not None, (
        "Need at least one personas_resource row as seed data"
    )

    result = await create_personas(
        conn, session_id=session.id, persona_ids=[persona_id]
    )

    items = await get_personas(conn, [result.id])

    assert len(items) == 1
    assert persona_id in items[0].persona_ids


async def test_create_with_multiple_connections(conn, profile_id):
    session = await _session(conn, profile_id)
    rows = await conn.fetch("SELECT id FROM personas_resource LIMIT 2")
    assert len(rows) >= 2, "Need at least two personas_resource rows as seed data"
    persona_ids = [r["id"] for r in rows]

    result = await create_personas(conn, session_id=session.id, persona_ids=persona_ids)

    items = await get_personas(conn, [result.id])

    assert len(items) == 1
    assert set(persona_ids) == set(items[0].persona_ids)
