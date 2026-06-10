"""Tests for set_cached — Redis cache writes with tag tracking."""

import json

import pytest

from app.utils.cache.invalidate_tags import invalidate_tags
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


async def test_short_ttl_write_does_not_shrink_tag_set_ttl(redis_client):
    """A later short-TTL write must NOT shrink a shared tag set's TTL.

    Regression: a plain EXPIRE overwrote the tag-set TTL with the writer's
    own ttl. A 30s write after a 300s write shrank the set to 30s, so when
    it expired early its still-live 300s members became unreachable by
    invalidate_tags (SMEMBERS), silently missing explicit invalidations.
    """
    # Long-lived dashboard key registered under the shared tag.
    await set_cached("key:long", {"x": 1}, 300, ["dash"], redis=redis_client)
    # A short-lived big-cache write hits the same tag afterward.
    await set_cached("key:short", {"y": 2}, 30, ["dash"], redis=redis_client)

    tag_ttl = await redis_client.ttl("http:tag:dash")
    # The tag set must outlive its longest-lived member (>= 300s), never 30s.
    assert tag_ttl > 30
    assert 290 < tag_ttl <= 300


async def test_short_ttl_write_keeps_long_key_invalidatable(redis_client):
    """After the short-TTL write, invalidate_tags still finds the long key."""
    await set_cached("key:long", {"x": 1}, 300, ["dash"], redis=redis_client)
    await set_cached("key:short", {"y": 2}, 30, ["dash"], redis=redis_client)

    # Tag set still contains the long-lived key (TTL was not shrunk away).
    members = await redis_client.smembers("http:tag:dash")
    assert b"key:long" in members

    await invalidate_tags(["dash"], redis=redis_client)
    assert await redis_client.get("key:long") is None


async def test_tag_set_always_gets_initial_ttl(redis_client):
    """A fresh tag set must receive a TTL (GT alone would orphan it).

    GT treats a key with no TTL as infinite and would never set one, so the
    NX flag must establish the initial expiry on a brand-new tag set.
    """
    await set_cached("key:1", {"x": 1}, 90, ["fresh"], redis=redis_client)

    tag_ttl = await redis_client.ttl("http:tag:fresh")
    assert 0 < tag_ttl <= 90
