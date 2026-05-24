"""Tests for create_point."""

import pytest

from app.tools.resources.points.create import create_point
from app.tools.resources.points.get import get_points

pytestmark = pytest.mark.asyncio


async def test_creates_new_point(conn, redis_client):
    result = await create_point(conn, 10, redis_client)

    assert result.value == 10
    assert result.active is True
    assert result.mcp is False


async def test_creates_point_with_custom_type(conn, redis_client):
    result = await create_point(conn, 15, redis_client, point_type="pass")

    assert result.value == 15


async def test_visible_via_get(conn, redis_client):
    result = await create_point(conn, 25, redis_client)

    items = await get_points(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 25


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_point(conn, 50, redis_client)
    second = await create_point(conn, 50, redis_client)

    assert first.id != second.id
    assert second.value == 50


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_point(conn, 100, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
