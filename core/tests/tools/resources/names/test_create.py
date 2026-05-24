"""Tests for create_name."""

import pytest

from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

pytestmark = pytest.mark.asyncio


async def test_creates_new_name(conn, redis_client):
    result = await create_name(conn, "test-name", redis_client)

    assert result.name == "test-name"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_name(conn, "test-name-visible", redis_client)

    items = await get_names(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-name-visible"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_name(conn, "duplicate-name", redis_client)
    second = await create_name(conn, "duplicate-name", redis_client)

    assert first.id == second.id
    assert second.name == "duplicate-name"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_name(conn, "mcp-name", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
