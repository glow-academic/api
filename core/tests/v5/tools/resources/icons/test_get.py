"""Tests for get_icons."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.icons.create import create_icon
from app.tools.resources.icons.get import get_icons

pytestmark = pytest.mark.asyncio


async def test_gets_created_icon(conn, redis_client):
    created = await create_icon(
        conn, "test-icon-for-get", "Test icon desc", "star", redis_client
    )

    items = await get_icons(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "test-icon-for-get"
    assert items[0].description == "Test icon desc"
    assert items[0].value == "star"
    assert items[0].active is True


async def test_returns_empty_for_missing_icon(conn, redis_client):
    items = await get_icons(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_icons(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_icon(
        conn, "test-icon-cache-hit", "desc", "circle", redis_client
    )

    items = await get_icons(conn, [created.id], redis_client)
    assert len(items) == 1

    items2 = await get_icons(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "test-icon-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_icon(
        conn, "test-icon-bypass", "desc", "square", redis_client
    )

    items = await get_icons(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/icons/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
