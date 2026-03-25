"""Tests for create_provider_key."""

import pytest

from app.tools.resources.keys.create import create_key
from app.tools.resources.provider_keys.create import create_provider_key
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.providers.create import create_provider

pytestmark = pytest.mark.asyncio


async def test_creates_new_provider_key(conn, redis_client):
    provider = await create_provider(conn, "test-provider", redis=redis_client)
    key = await create_key(conn, redis_client, name="test-key", key="sk-test-123")
    result = await create_provider_key(
        conn,
        provider.id,
        key.id,
        redis_client,
        key="sk-pk-123",
        name="test-pk",
        description="Test pk desc",
    )

    assert result.provider_id == provider.id
    assert result.key_id == key.id
    assert result.key == "sk-pk-123"
    assert result.name == "test-pk"
    assert result.description == "Test pk desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    provider = await create_provider(conn, "test-provider-visible", redis=redis_client)
    key = await create_key(
        conn, redis_client, name="test-key-visible", key="sk-visible-123"
    )
    result = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="visible-pk"
    )

    items = await get_provider_keys(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "visible-pk"


async def test_creates_second_row(conn, redis_client):
    provider = await create_provider(conn, "test-provider-second", redis=redis_client)
    key = await create_key(
        conn, redis_client, name="test-key-second", key="sk-second-123"
    )
    first = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="pk-first"
    )
    second = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="pk-second"
    )

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    provider = await create_provider(conn, "test-provider-mcp", redis=redis_client)
    key = await create_key(conn, redis_client, name="test-key-mcp", key="sk-mcp-123")
    result = await create_provider_key(
        conn, provider.id, key.id, redis_client, name="mcp-pk", mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
