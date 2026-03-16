"""Tests for set_cached — Redis cache writes with tag tracking."""

import json

import pytest

from app.utils.cache.set_cached import set_cached

pytestmark = pytest.mark.asyncio


async def test_stores_data_with_ttl(redis_client):
    data = {"items": [{"id": "abc"}]}

    await set_cached("test:key", data, 60, ["tag1"], redis=redis_client)

    raw = await redis_client.get("test:key")
    assert json.loads(raw) == data
    ttl = await redis_client.ttl("test:key")
    assert 0 < ttl <= 60


async def test_tracks_key_in_tag_sets(redis_client):
    await set_cached("test:key", {"x": 1}, 60, ["tag1", "tag2"], redis=redis_client)

    members1 = await redis_client.smembers("http:tag:tag1")
    members2 = await redis_client.smembers("http:tag:tag2")

    assert b"test:key" in members1
    assert b"test:key" in members2


async def test_tag_sets_expire(redis_client):
    await set_cached("test:key", {"x": 1}, 120, ["mytag"], redis=redis_client)

    ttl = await redis_client.ttl("http:tag:mytag")
    assert 0 < ttl <= 120


async def test_multiple_keys_same_tag(redis_client):
    await set_cached("key:1", {"a": 1}, 60, ["shared"], redis=redis_client)
    await set_cached("key:2", {"b": 2}, 60, ["shared"], redis=redis_client)

    members = await redis_client.smembers("http:tag:shared")
    assert {b"key:1", b"key:2"} == members
