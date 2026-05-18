"""Tests for create_auth_item_key."""

import pytest

from app.tools.resources.auth_item_keys.create import create_auth_item_key
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auths.create import create_auth
from app.tools.resources.items.create import create_item
from app.tools.resources.keys.create import create_key

pytestmark = pytest.mark.asyncio


async def test_creates_new_auth_item_key(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth")
    item = await create_item(conn, "item", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key")
    result = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    assert result.auth_id == auth.id
    assert result.item_id == item.id
    assert result.key_id == key.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth-visible")
    item = await create_item(conn, "item-visible", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key-visible")
    result = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    items = await get_auth_item_keys(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].auth_id == auth.id


async def test_returns_existing_on_conflict(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth-conflict")
    item = await create_item(conn, "item-conflict", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key-conflict")
    first = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)
    second = await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)

    assert first.id == second.id


async def test_sets_mcp_flag(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="test-auth-mcp")
    item = await create_item(conn, "item-mcp", "desc", redis_client)
    key = await create_key(conn, redis_client, name="test-key-mcp")
    result = await create_auth_item_key(
        conn, auth.id, item.id, key.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
