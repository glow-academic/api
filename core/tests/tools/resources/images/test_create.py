"""Tests for create_image."""

import pytest

from app.tools.resources.images.create import create_image
from app.tools.resources.images.get import get_images

pytestmark = pytest.mark.asyncio


async def test_creates_new_image(conn, redis_client):
    result = await create_image(conn, "test-image", "An image", redis_client)

    assert result.name == "test-image"
    assert result.description == "An image"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_image(conn, "test-image-visible", "desc", redis_client)

    items = await get_images(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_image(conn, "duplicate-image", "desc", redis_client)
    second = await create_image(conn, "duplicate-image", "desc", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_image(conn, "mcp-image", "desc", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
