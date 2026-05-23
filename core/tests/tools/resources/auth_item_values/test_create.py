
"""Tests for create_auth_item_value."""

import pytest

from app.tools.resources.auth_item_values.create import create_auth_item_value
from app.tools.resources.auth_item_values.get import get_auth_item_values
from app.tools.resources.auths.create import create_auth
from app.tools.resources.items.create import create_item

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_creates_new_auth_item_value(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-value")
    item = await create_item(conn, "value-item", "desc", redis_client)

    result = await create_auth_item_value(
        conn,
        auth.id,
        item.id,
        "secret-value",
        redis_client,
    )

    assert result.auth_id == auth.id
    assert result.item_id == item.id
    assert result.value == "secret-value"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-visible")
    item = await create_item(conn, "value-item-visible", "desc", redis_client)
    result = await create_auth_item_value(
        conn,
        auth.id,
        item.id,
        "visible-value",
        redis_client,
    )

    items = await get_auth_item_values(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == "visible-value"


async def test_returns_existing_on_conflict(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-conflict")
    item = await create_item(conn, "value-item-conflict", "desc", redis_client)
    first = await create_auth_item_value(conn, auth.id, item.id, "same-value", redis_client)
    second = await create_auth_item_value(conn, auth.id, item.id, "same-value", redis_client)

    assert first.id == second.id


async def test_sets_mcp_flag(conn, redis_client):
    auth = await create_auth(conn, redis_client, name="auth-item-mcp")
    item = await create_item(conn, "value-item-mcp", "desc", redis_client)
    result = await create_auth_item_value(
        conn,
        auth.id,
        item.id,
        "mcp-value",
        redis_client,
        mcp=True,
    )

    assert result.mcp is True
    assert result.generated is True
