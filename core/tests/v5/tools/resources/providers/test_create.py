"""Tests for create_provider."""

import pytest

from app.tools.resources.providers.create import create_provider
from app.tools.resources.providers.get import get_providers

pytestmark = pytest.mark.asyncio


async def test_creates_new_provider(conn, redis_client):
    result = await create_provider(conn, "test-provider", "desc", redis_client)

    assert result.name == "test-provider"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_provider(conn, "test-provider-visible", redis=redis_client)

    items = await get_providers(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-provider-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_provider(conn, "test-provider-dup", redis=redis_client)
    second = await create_provider(conn, "test-provider-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_provider(conn, "mcp-provider", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
