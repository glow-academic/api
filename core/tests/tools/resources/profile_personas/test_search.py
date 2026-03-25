"""Tests for search_profile_personas."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.personas.create import create_persona
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profile_personas.search import (
    search_profile_personas,
)
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def _create_profile_persona_with_deps(conn, redis_client):
    """Helper: create a profile + persona + profile_persona."""
    profile = await create_profile(conn, redis_client, name=f"profile-{unique_tag()}")
    persona = await create_persona(conn, redis_client, name=f"persona-{unique_tag()}")
    pp = await create_profile_persona(conn, profile.id, persona.id, redis_client)
    return pp


async def test_finds_created_profile_persona(conn, redis_client):
    pp = await _create_profile_persona_with_deps(conn, redis_client)

    items = await search_profile_personas(conn, redis_client, limit_count=1000)

    ids = [i.id for i in items]
    assert pp.id in ids


async def test_respects_limit(conn, redis_client):
    for _ in range(3):
        await _create_profile_persona_with_deps(conn, redis_client)

    items = await search_profile_personas(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for _ in range(3):
        await _create_profile_persona_with_deps(conn, redis_client)

    all_items = await search_profile_personas(conn, redis_client, limit_count=1000)
    offset_items = await search_profile_personas(
        conn, redis_client, limit_count=1000, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await _create_profile_persona_with_deps(conn, redis_client)
    b = await _create_profile_persona_with_deps(conn, redis_client)

    items = await search_profile_personas(
        conn, redis_client, limit_count=1000, exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_profile_personas(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_profile_persona_with_deps(conn, redis_client)

    items1 = await search_profile_personas(conn, redis_client, limit_count=1000)
    items2 = await search_profile_personas(conn, redis_client, limit_count=1000)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_profile_persona_with_deps(conn, redis_client)

    items = await search_profile_personas(
        conn, redis_client, limit_count=1000, bypass_cache=True
    )

    assert len(items) >= 1
