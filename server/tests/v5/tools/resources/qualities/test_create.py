"""Tests for create_quality."""

import pytest

from app.tools.resources.qualities.create import create_quality
from app.tools.resources.qualities.get import get_qualities

pytestmark = pytest.mark.asyncio


async def test_creates_new_quality(conn, redis_client):
    result = await create_quality(conn, "low", redis_client)

    assert result.quality == "low"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_quality(conn, "medium", redis_client)

    items = await get_qualities(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].quality == "medium"


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_quality(conn, "high", redis_client)
    second = await create_quality(conn, "high", redis_client)

    assert first.id != second.id
    assert second.quality == "high"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_quality(conn, "low", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
