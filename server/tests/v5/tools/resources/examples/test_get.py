"""Tests for get_examples."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.examples.create import create_example
from app.tools.resources.examples.get import get_examples

pytestmark = pytest.mark.asyncio


async def test_gets_created_example(conn, redis_client):
    created = await create_example(conn, "test-example-for-get", redis_client)

    items = await get_examples(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].example == "test-example-for-get"
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_examples(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_examples(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_example(conn, "test-example-cache-hit", redis_client)

    # First call populates cache
    items = await get_examples(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_examples(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].example == "test-example-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_example(conn, "test-example-bypass", redis_client)

    items = await get_examples(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/examples/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
