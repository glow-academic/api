"""Tests for get_standards."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standards.create import create_standard
from app.tools.resources.standards.get import get_standards

pytestmark = pytest.mark.asyncio


async def test_gets_created_standard(conn, redis_client):
    sg = await create_standard_group(
        conn, "Test Group", "TG", "desc", 100, 70, redis_client
    )
    item = await create_standard(conn, "Test Standard", "desc", 10, sg.id, redis_client)

    items = await get_standards(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].name == "Test Standard"
    assert items[0].description == "desc"
    assert items[0].points == 10
    assert items[0].standard_group_id == sg.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_standards(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_standards(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    sg = await create_standard_group(
        conn, "Test Group Cache", "TGC", "desc", 100, 70, redis_client
    )
    item = await create_standard(
        conn, "Test Standard Cache", "desc", 10, sg.id, redis_client
    )

    # First call populates cache
    items = await get_standards(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_standards(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    sg = await create_standard_group(
        conn, "Test Group Bypass", "TGB", "desc", 100, 70, redis_client
    )
    item = await create_standard(
        conn, "Test Standard Bypass", "desc", 10, sg.id, redis_client
    )

    items = await get_standards(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/standards/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
