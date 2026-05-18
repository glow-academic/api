"""Tests for create_description."""

import pytest

from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions

pytestmark = pytest.mark.asyncio


async def test_creates_new_description(conn, redis_client):
    result = await create_description(conn, "test-description", redis_client)

    assert result.description == "test-description"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_description(conn, "test-description-visible", redis_client)

    items = await get_descriptions(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_description(conn, "duplicate-description", redis_client)
    second = await create_description(conn, "duplicate-description", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_description(conn, "mcp-description", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
