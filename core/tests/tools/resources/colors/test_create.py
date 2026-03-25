"""Tests for create_color."""

import pytest

from app.tools.resources.colors.create import create_color
from app.tools.resources.colors.get import get_colors

pytestmark = pytest.mark.asyncio


async def test_creates_new_color(conn, redis_client):
    result = await create_color(conn, "test-color", "A color", "#AABBCC", redis_client)

    assert result.name == "test-color"
    assert result.description == "A color"
    assert result.hex_code == "#AABBCC"
    assert result.type == "primary"
    assert result.active is True
    assert result.mcp is False


async def test_creates_color_with_custom_type(conn, redis_client):
    result = await create_color(
        conn, "typed-color", "desc", "#112233", redis_client, color_type="accent"
    )

    assert result.type == "accent"


async def test_visible_via_get(conn, redis_client):
    result = await create_color(
        conn, "test-color-visible", "desc", "#123456", redis_client
    )

    items = await get_colors(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_color(conn, "duplicate-color", "desc", "#111111", redis_client)
    second = await create_color(
        conn, "duplicate-color", "desc", "#111111", redis_client
    )

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_color(
        conn, "mcp-color", "desc", "#FFFFFF", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
