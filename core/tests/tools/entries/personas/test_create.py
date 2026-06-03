"""Tests for create_personas."""

import pytest

from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session
from app.tools.resources.personas.create import create_persona

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_create_returns_id(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_personas(conn, redis_client, session_id=session.id)

    assert result.id is not None


async def test_roundtrip_base_fields(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_personas(conn, redis_client, session_id=session.id)

    items = await get_personas(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].generated is True
    assert items[0].mcp is False


async def test_create_without_connections_returns_empty_list(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_personas(conn, redis_client, session_id=session.id)

    items = await get_personas(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].persona_ids == []


async def test_create_with_connections(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    persona = await create_persona(conn, redis_client, name="test-persona")
    persona_id = persona.id

    result = await create_personas(
        conn, redis_client, session_id=session.id, persona_ids=[persona_id]
    )

    items = await get_personas(conn, [result.id], redis_client)

    assert len(items) == 1
    assert persona_id in items[0].persona_ids


async def test_create_with_multiple_connections(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    p1 = await create_persona(conn, redis_client, name="test-persona-1")
    p2 = await create_persona(conn, redis_client, name="test-persona-2")
    persona_ids = [p1.id, p2.id]

    result = await create_personas(conn, redis_client, session_id=session.id, persona_ids=persona_ids)

    items = await get_personas(conn, [result.id], redis_client)

    assert len(items) == 1
    assert set(persona_ids) == set(items[0].persona_ids)
