"""Tests for get_provider_keys."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.keys.create import create_key
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.providers.create import create_provider

pytestmark = pytest.mark.asyncio


async def test_gets_created_provider_key(conn, redis_client):
    provider = await create_provider(conn, "test-provider", redis=redis_client)
    key = await create_key(conn, redis_client, name="test-key", key="sk-test-123")
    from app.tools.resources.provider_keys.create import create_provider_key

    item = await create_provider_key(
        conn,
        provider.id,
        key.id,
        redis_client,
        key="sk-pk-123",
        name="test-pk",
        description="Test pk desc",
    )

    items = await get_provider_keys(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].provider_id == provider.id
    assert items[0].key_id == key.id
    assert items[0].key == "sk-pk-123"
    assert items[0].name == "test-pk"
    assert items[0].description == "Test pk desc"
    assert items[0].active is True


async def test_returns_empty_for_missing_provider_key(conn, redis_client):
    items = await get_provider_keys(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_provider_keys(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    provider = await create_provider(conn, "test-provider-cache", redis=redis_client)
    key = await create_key(
        conn, redis_client, name="test-key-cache", key="sk-cache-123"
    )
    from app.tools.resources.provider_keys.create import create_provider_key

    item = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="test-pk-cache-hit"
    )

    # First call populates cache
    items = await get_provider_keys(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_provider_keys(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "test-pk-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    provider = await create_provider(conn, "test-provider-bypass", redis=redis_client)
    key = await create_key(
        conn, redis_client, name="test-key-bypass", key="sk-bypass-123"
    )
    from app.tools.resources.provider_keys.create import create_provider_key

    item = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="test-pk-bypass"
    )

    items = await get_provider_keys(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key_val = cache_key("/v5/resources/provider_keys/get", {"ids": [str(item.id)]})
    cached = await get_cached(key_val, redis=redis_client)
    assert cached is None
