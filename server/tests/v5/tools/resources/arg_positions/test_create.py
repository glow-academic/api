"""Tests for create_arg_position."""

import pytest

from app.tools.resources.arg_positions.create import create_arg_position
from app.tools.resources.arg_positions.get import get_arg_positions
from app.tools.resources.args.create import create_arg

pytestmark = pytest.mark.asyncio


async def test_creates_new_arg_position(conn, redis_client):
    arg = await create_arg(conn, "test-arg", "text", redis_client)
    result = await create_arg_position(conn, arg.id, 1, redis_client)

    assert result.args_id == arg.id
    assert result.value == 1
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    arg = await create_arg(conn, "test-arg-visible", "text", redis_client)
    result = await create_arg_position(conn, arg.id, 5, redis_client)

    items = await get_arg_positions(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 5


async def test_creates_second_row(conn, redis_client):
    arg = await create_arg(conn, "test-arg-second", "text", redis_client)
    first = await create_arg_position(conn, arg.id, 1, redis_client)
    second = await create_arg_position(conn, arg.id, 1, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    arg = await create_arg(conn, "test-arg-mcp", "text", redis_client)
    result = await create_arg_position(conn, arg.id, 10, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
