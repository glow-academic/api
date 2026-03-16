"""Tests for get_profile_personas."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.personas.create import create_persona
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def test_gets_created_profile_persona(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile")
    persona = await create_persona(conn, redis_client, name="test-persona")
    item = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    items = await get_profile_personas(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].profile_id == profile.id
    assert items[0].persona_id == persona.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_profile_personas(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_profile_personas(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile-cache")
    persona = await create_persona(conn, redis_client, name="test-persona-cache")
    item = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    # First call populates cache
    items = await get_profile_personas(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_profile_personas(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    profile = await create_profile(conn, redis_client, name="test-profile-bypass")
    persona = await create_persona(conn, redis_client, name="test-persona-bypass")
    item = await create_profile_persona(conn, profile.id, persona.id, redis_client)

    items = await get_profile_personas(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/profile_personas/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
