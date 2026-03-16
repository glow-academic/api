"""Tests for get_profiles."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.profiles.create import create_profile
from app.tools.resources.profiles.get import get_profiles

pytestmark = pytest.mark.asyncio


async def test_gets_created_profile(conn, redis_client):
    created = await create_profile(
        conn, redis_client, name="test-profile", description="Test profile desc"
    )

    items = await get_profiles(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "test-profile"
    assert items[0].description == "Test profile desc"
    assert items[0].department_ids == []
    assert items[0].emails == []
    assert items[0].active is True


async def test_returns_empty_for_missing_profile(conn, redis_client):
    items = await get_profiles(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_profiles(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_profile(conn, redis_client, name="test-profile-cache-hit")

    # First call populates cache
    items = await get_profiles(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_profiles(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "test-profile-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_profile(conn, redis_client, name="test-profile-bypass")

    items = await get_profiles(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/profiles/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
