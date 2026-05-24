"""Tests for create_arg."""

import pytest

from app.tools.resources.args.create import create_arg
from app.tools.resources.args.get import get_args

pytestmark = pytest.mark.asyncio


async def test_creates_new_arg(conn, redis_client):
    result = await create_arg(conn, "test-arg", "string", redis_client)

    assert result.name == "test-arg"
    assert result.field_type == "string"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_arg(conn, "test-arg-visible", "integer", redis_client)

    items = await get_args(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-arg-visible"


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_arg(conn, "duplicate-arg", "string", redis_client)
    second = await create_arg(conn, "duplicate-arg", "string", redis_client)

    assert first.id != second.id
    assert second.name == "duplicate-arg"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_arg(conn, "mcp-arg", "boolean", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
