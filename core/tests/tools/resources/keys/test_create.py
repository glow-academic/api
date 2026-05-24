"""Tests for create_key."""

import pytest

from app.tools.resources.keys.create import create_key
from app.tools.resources.keys.get import get_keys

pytestmark = pytest.mark.asyncio


async def test_creates_new_key(conn, redis_client):
    result = await create_key(conn, redis_client, name="test-key")

    assert result.name == "test-key"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_key(
        conn, redis_client, name="test-key-visible", key="sk-visible"
    )

    items = await get_keys(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-key-visible"


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_key(conn, redis_client, name="duplicate-key")
    second = await create_key(conn, redis_client, name="duplicate-key")

    assert first.id != second.id
    assert second.name == "duplicate-key"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_key(conn, redis_client, name="mcp-key", mcp=True)

    assert result.mcp is True
    assert result.generated is True
