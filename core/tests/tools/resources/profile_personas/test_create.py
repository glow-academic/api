"""Tests for create_profile_persona."""

import pytest

from app.tools.resources.personas.create import create_persona
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def test_creates_new_profile_persona(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile")
    persona = await create_persona(conn, redis_client, name="test-persona")
    result = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    assert result.profile_id == profile.id
    assert result.persona_id == persona.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile-visible")
    persona = await create_persona(conn, redis_client, name="test-persona-visible")
    result = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    items = await get_profile_personas(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].profile_id == profile.id
    assert items[0].persona_id == persona.id


async def test_returns_existing_on_conflict(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile-conflict")
    persona = await create_persona(conn, redis_client, name="test-persona-conflict")
    first = await create_profile_persona(conn, profile.id, persona.id, redis_client)
    second = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    assert first.id == second.id


async def test_sets_mcp_flag(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile-mcp")
    persona = await create_persona(conn, redis_client, name="test-persona-mcp")
    result = await create_profile_persona(
        conn, profile.id, persona.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
