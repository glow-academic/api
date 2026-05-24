"""Tests for create_args_output."""

import pytest

from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.create import create_args_output
from app.tools.resources.args_outputs.get import get_args_outputs

pytestmark = pytest.mark.asyncio


async def test_creates_new_args_output(conn, redis_client):
    arg = await create_arg(conn, "test-arg", "text", redis_client)
    result = await create_args_output(conn, arg.id, "output-name", redis_client)

    assert result.args_id == arg.id
    assert result.name == "output-name"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    arg = await create_arg(conn, "test-arg-visible", "text", redis_client)
    result = await create_args_output(conn, arg.id, "visible-output", redis_client)

    items = await get_args_outputs(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "visible-output"


async def test_creates_second_row(conn, redis_client):
    arg1 = await create_arg(conn, "test-arg-first", "text", redis_client)
    arg2 = await create_arg(conn, "test-arg-second", "text", redis_client)
    first = await create_args_output(conn, arg1.id, "output-name", redis_client)
    second = await create_args_output(conn, arg2.id, "output-name", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    arg = await create_arg(conn, "test-arg-mcp", "text", redis_client)
    result = await create_args_output(
        conn, arg.id, "mcp-output", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
