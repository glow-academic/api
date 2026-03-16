"""Tests for get_cached — Redis cache reads."""

import json

import pytest

from app.utils.cache.get_cached import get_cached

pytestmark = pytest.mark.asyncio


async def test_returns_none_on_cache_miss(redis_client):
    result = await get_cached("nonexistent:key", redis=redis_client)

    assert result is None


async def test_returns_cached_dict_on_hit(redis_client):
    data = {"items": [{"id": "abc", "name": "test"}]}
    await redis_client.set("test:key", json.dumps(data))

    result = await get_cached("test:key", redis=redis_client)

    assert result == data


async def test_handles_bytes_response(redis_client):
    data = {"items": []}
    await redis_client.set("test:bytes", json.dumps(data).encode("utf-8"))

    result = await get_cached("test:bytes", redis=redis_client)

    assert result == data


async def test_returns_none_on_expired_key(redis_client):
    await redis_client.setex("test:expired", 1, json.dumps({"x": 1}))
    await redis_client.delete("test:expired")

    result = await get_cached("test:expired", redis=redis_client)

    assert result is None
