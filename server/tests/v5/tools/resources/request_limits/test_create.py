"""Tests for create_request_limit."""

import pytest

from app.tools.resources.request_limits.create import create_request_limit
from app.tools.resources.request_limits.get import get_request_limits

pytestmark = pytest.mark.asyncio


async def test_creates_new_request_limit(conn, redis_client):
    result = await create_request_limit(conn, 100, redis_client)

    assert result.requests_per_day == 100
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_request_limit(conn, 250, redis_client)

    items = await get_request_limits(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].requests_per_day == 250


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_request_limit(conn, 1000, redis_client)
    second = await create_request_limit(conn, 1000, redis_client)

    assert first.id != second.id
    assert second.requests_per_day == 1000


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_request_limit(conn, 50, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
