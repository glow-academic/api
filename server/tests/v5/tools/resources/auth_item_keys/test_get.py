"""Tests for get_auth_item_keys."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.auth_item_keys.create import create_auth_item_key
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auths.create import create_auth
from app.tools.resources.items.create import create_item
from app.tools.resources.keys.create import create_key

pytestmark = pytest.mark.asyncio


async def test_gets_created_auth_item_key(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth")
    item = await create_item(conn, "item", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key")
    row = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    items = await get_auth_item_keys(conn, [row.id], redis_client)

    assert len(items) == 1
    assert items[0].id == row.id
    assert items[0].auth_id == auth.id
    assert items[0].item_id == item.id
    assert items[0].key_id == key.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_auth_item_keys(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_auth_item_keys(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth-cache")
    item = await create_item(conn, "item-cache", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key-cache")
    row = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    # First call populates cache
    items = await get_auth_item_keys(conn, [row.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_auth_item_keys(conn, [row.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == row.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth-bypass")
    item = await create_item(conn, "item-bypass", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key-bypass")
    row = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    items = await get_auth_item_keys(conn, [row.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key_str = cache_key("/v5/resources/auth_item_keys/get", {"ids": [str(row.id)]})
    cached = await get_cached(key_str, redis=redis_client)
    assert cached is None
