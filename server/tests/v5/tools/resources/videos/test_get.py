"""Tests for get_videos."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.videos.create import create_video
from app.tools.resources.videos.get import get_videos

pytestmark = pytest.mark.asyncio


async def test_gets_created_video(conn, redis_client):
    created = await create_video(
        conn, "test-video-for-get", "Test video desc", redis_client
    )

    items = await get_videos(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "test-video-for-get"
    assert items[0].description == "Test video desc"
    assert items[0].active is True


async def test_returns_empty_for_missing_video(conn, redis_client):
    items = await get_videos(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_videos(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_video(conn, "test-video-cache-hit", "desc", redis_client)

    items = await get_videos(conn, [created.id], redis_client)
    assert len(items) == 1

    items2 = await get_videos(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "test-video-cache-hit"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_video(conn, "test-video-bypass", "desc", redis_client)

    items = await get_videos(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/videos/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
