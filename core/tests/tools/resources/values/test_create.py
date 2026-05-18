"""Tests for create_value."""

import pytest

from app.tools.resources.values.create import create_value
from app.tools.resources.values.get import get_values

pytestmark = pytest.mark.asyncio


async def test_creates_new_value(conn, redis_client):
    result = await create_value(conn, "test-value", redis_client)

    assert result.value == "test-value"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_value(conn, "test-value-visible", redis_client)

    items = await get_values(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == "test-value-visible"


async def test_creates_second_row(conn, redis_client):
    first = await create_value(conn, "duplicate-value", redis_client)
    second = await create_value(conn, "duplicate-value", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_value(conn, "mcp-value", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
