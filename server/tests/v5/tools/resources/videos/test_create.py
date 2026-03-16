"""Tests for create_video."""

import pytest

from app.tools.resources.videos.create import create_video
from app.tools.resources.videos.get import get_videos

pytestmark = pytest.mark.asyncio


async def test_creates_new_video(conn, redis_client):
    result = await create_video(conn, "test-video", "A video", redis_client)

    assert result.name == "test-video"
    assert result.description == "A video"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_video(conn, "test-video-visible", "desc", redis_client)

    items = await get_videos(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_video(conn, "duplicate-video", "desc", redis_client)
    second = await create_video(conn, "duplicate-video", "desc", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_video(conn, "mcp-video", "desc", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
