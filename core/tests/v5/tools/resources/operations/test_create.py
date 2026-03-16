"""Tests for create_operation."""

import pytest

from app.tools.resources.operations.create import create_operation
from app.tools.resources.operations.get import get_operations

pytestmark = pytest.mark.asyncio


async def test_creates_new_operation(conn, redis_client):
    result = await create_operation(conn, "get", redis_client)

    assert result.operation is not None
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_operation(conn, "search", redis_client)

    items = await get_operations(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].operation == result.operation


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_operation(conn, "create", redis_client)
    second = await create_operation(conn, "create", redis_client)

    assert first.id == second.id
    assert second.operation == "create"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_operation(conn, "update", redis_client, mcp=True)

    assert result.operation == "update"
    assert result.id is not None
