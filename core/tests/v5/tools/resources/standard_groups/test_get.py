"""Tests for get_standard_groups."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standard_groups.get import get_standard_groups

pytestmark = pytest.mark.asyncio


async def test_gets_created_standard_group(conn, redis_client):
    created = await create_standard_group(
        conn, "Test Group", "TG", "desc", 100, 70, redis_client
    )

    items = await get_standard_groups(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "Test Group"
    assert items[0].short_name == "TG"
    assert items[0].description == "desc"
    assert items[0].points == 100
    assert items[0].pass_points == 70
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_standard_groups(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_standard_groups(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_standard_group(
        conn, "Cache Group", "CG", "cache desc", 50, 35, redis_client
    )

    # First call populates cache
    items = await get_standard_groups(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_standard_groups(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "Cache Group"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_standard_group(
        conn, "Bypass Group", "BG", "bypass desc", 80, 60, redis_client
    )

    items = await get_standard_groups(
        conn, [created.id], redis_client, bypass_cache=True
    )
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/standard_groups/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
