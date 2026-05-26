"""Tests for search_personas."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.persona.create import create_persona
from app.tools.entries.persona.refresh import refresh_persona_internal
from app.tools.entries.persona.search import search_personas
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def test_finds_created_entry(conn, redis_client):
    result = await create_persona(conn, redis_client)
    await refresh_persona_internal(conn)

    items = await search_personas(conn, redis_client)

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session_id(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    await conn.execute(
        "INSERT INTO personas_entry (session_id, generated) VALUES ($1, true)",
        session.id,
    )
    await refresh_persona_internal(conn)

    items = await search_personas(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client):
    await create_persona(conn, redis_client)
    await create_persona(conn, redis_client)
    await refresh_persona_internal(conn)

    items = await search_personas(conn, redis_client, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client):
    await create_persona(conn, redis_client)
    await refresh_persona_internal(conn)

    items = await search_personas(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client):
    result = await create_persona(conn, redis_client)

    items = await search_personas(conn, redis_client, bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
