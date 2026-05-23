
"""Tests for get_auth_item_values."""

import pytest

from app.tools.resources.auth_item_values.create import create_auth_item_value
from app.tools.resources.auth_item_values.get import get_auth_item_values
from app.tools.resources.auths.create import create_auth
from app.tools.resources.items.create import create_item
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_gets_created_auth_item_value(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-get")
    item = await create_item(conn, "value-item-get", "desc", redis_client)
    row = await create_auth_item_value(conn, auth.id, item.id, "get-value", redis_client)

    items = await get_auth_item_values(conn, [row.id], redis_client)

    assert len(items) == 1
    assert items[0].id == row.id
    assert items[0].auth_id == auth.id
    assert items[0].item_id == item.id
    assert items[0].value == "get-value"


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_auth_item_values(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_auth_item_values(conn, [], redis_client)

    assert items == []


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-bypass")
    item = await create_item(conn, "value-item-bypass", "desc", redis_client)
    row = await create_auth_item_value(conn, auth.id, item.id, "bypass-value", redis_client)

    items = await get_auth_item_values(conn, [row.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    key = cache_key('/resources/auth_item_values/get', {'ids': [str(row.id)]})
    assert await get_cached(key, redis=redis_client) is None
