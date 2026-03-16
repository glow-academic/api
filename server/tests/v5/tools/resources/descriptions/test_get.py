"""Tests for get_descriptions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions

pytestmark = pytest.mark.asyncio


async def test_gets_created_description(conn, redis_client):
    created = await create_description(conn, "test-description-for-get", redis_client)

    items = await get_descriptions(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].description == "test-description-for-get"
    assert items[0].active is True


async def test_returns_empty_for_missing_description(conn, redis_client):
    items = await get_descriptions(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_descriptions(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_description(conn, "test-description-cache-hit", redis_client)

    items = await get_descriptions(conn, [created.id], redis_client)
    assert len(items) == 1

    items2 = await get_descriptions(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].description == "test-description-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_description(conn, "test-description-bypass", redis_client)

    items = await get_descriptions(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/descriptions/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
