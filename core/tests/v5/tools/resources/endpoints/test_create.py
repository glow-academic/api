"""Tests for create_endpoint."""

import pytest

from app.tools.resources.endpoints.create import create_endpoint
from app.tools.resources.endpoints.get import get_endpoints

pytestmark = pytest.mark.asyncio


async def test_creates_new_endpoint(conn, redis_client):
    result = await create_endpoint(conn, "https://test.example.com", redis_client)

    assert result.base_url == "https://test.example.com"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_endpoint(conn, "https://visible.example.com", redis_client)

    items = await get_endpoints(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].base_url == "https://visible.example.com"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_endpoint(conn, "https://duplicate.example.com", redis_client)
    second = await create_endpoint(conn, "https://duplicate.example.com", redis_client)

    assert first.id == second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_endpoint(
        conn, "https://mcp.example.com", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
