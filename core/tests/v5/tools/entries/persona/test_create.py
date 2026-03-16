"""Tests for create_persona."""

import pytest

from app.tools.entries.persona.create import create_persona
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)

pytestmark = pytest.mark.asyncio


async def test_returns_id(conn):
    result = await create_persona(conn)

    assert result.id is not None


async def test_links_personas_resource(conn, redis_client):
    linked_persona = await create_persona_resource(conn, redis=redis_client)
    result = await create_persona(conn, personas_id=linked_persona.id)

    row = await conn.fetchrow(
        "SELECT personas_id FROM personas_personas_connection WHERE personas_entry_id = $1",
        result.id,
    )
    assert row is not None
    assert row["personas_id"] == linked_persona.id


async def test_passes_mcp_flag(conn):
    result = await create_persona(conn, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM personas_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
