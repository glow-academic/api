"""Tests for invalidate_tags — Redis cache invalidation."""

import pytest

from app.utils.cache.get_cached import get_cached
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.cache.set_cached import set_cached

pytestmark = pytest.mark.asyncio


async def test_deletes_cached_keys_for_tag(redis_client):
    await set_cached("key:1", {"a": 1}, 60, ["resources"], redis=redis_client)
    await set_cached("key:2", {"b": 2}, 60, ["resources"], redis=redis_client)

    await invalidate_tags(["resources"], redis=redis_client)

    assert await get_cached("key:1", redis=redis_client) is None
    assert await get_cached("key:2", redis=redis_client) is None


async def test_deletes_tag_set_itself(redis_client):
    await set_cached("key:1", {"a": 1}, 60, ["names"], redis=redis_client)

    await invalidate_tags(["names"], redis=redis_client)

    exists = await redis_client.exists("http:tag:names")
    assert exists == 0


async def test_invalidates_multiple_tags(redis_client):
    await set_cached("key:a", {"x": 1}, 60, ["tag1"], redis=redis_client)
    await set_cached("key:b", {"y": 2}, 60, ["tag2"], redis=redis_client)

    await invalidate_tags(["tag1", "tag2"], redis=redis_client)

    assert await get_cached("key:a", redis=redis_client) is None
    assert await get_cached("key:b", redis=redis_client) is None


async def test_leaves_unrelated_keys(redis_client):
    await set_cached("key:keep", {"keep": 1}, 60, ["safe"], redis=redis_client)
    await set_cached("key:del", {"del": 1}, 60, ["doomed"], redis=redis_client)

    await invalidate_tags(["doomed"], redis=redis_client)

    assert await get_cached("key:keep", redis=redis_client) == {"keep": 1}
    assert await get_cached("key:del", redis=redis_client) is None


async def test_noop_for_empty_tags(redis_client):
    await set_cached("key:safe", {"x": 1}, 60, ["safe"], redis=redis_client)

    await invalidate_tags([], redis=redis_client)

    assert await get_cached("key:safe", redis=redis_client) == {"x": 1}
