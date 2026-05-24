"""Tests for create_threshold."""

import pytest

from app.tools.resources.thresholds.create import create_threshold
from app.tools.resources.thresholds.get import get_thresholds

pytestmark = pytest.mark.asyncio


async def test_creates_new_threshold(conn, redis_client):
    result = await create_threshold(conn, 80, redis_client)

    assert result.value == 80
    assert result.type == "success"
    assert result.active is True
    assert result.mcp is False


async def test_creates_threshold_with_custom_type(conn, redis_client):
    result = await create_threshold(conn, 60, redis_client, threshold_type="warning")

    assert result.type == "warning"


async def test_visible_via_get(conn, redis_client):
    result = await create_threshold(conn, 70, redis_client)

    items = await get_thresholds(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 70


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_threshold(conn, 90, redis_client)
    second = await create_threshold(conn, 90, redis_client)

    assert first.id != second.id
    assert second.value == 90


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_threshold(conn, 50, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
