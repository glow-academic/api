"""Tests for create_tool."""

import pytest

from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.create import create_args_output
from app.tools.resources.artifacts.create import create_artifact
from app.tools.resources.departments.create import create_department
from app.tools.resources.operations.create import create_operation
from app.tools.resources.tools.create import create_tool
from app.tools.resources.tools.get import get_tools

pytestmark = pytest.mark.asyncio


async def test_creates_new_tool(conn, redis_client):
    result = await create_tool(conn, "test-tool", "desc", redis_client)

    assert result.name == "test-tool"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_tool(conn, "test-tool-visible", redis=redis_client)

    items = await get_tools(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-tool-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_tool(conn, "test-tool-dup", redis=redis_client)
    second = await create_tool(conn, "test-tool-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_tool(conn, "mcp-tool", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_round_trips_operation_targets_and_departments(conn, redis_client):
    department = await create_department(conn, "tool-dept", redis=redis_client)
    operation = await create_operation(conn, "create", redis_client)
    artifact = await create_artifact(conn, "profile", redis_client)

    result = await create_tool(
        conn,
        "linked-tool",
        redis=redis_client,
        department_ids=[department.id],
        operation=operation.operation,
        artifacts=[artifact.artifact],
    )

    items = await get_tools(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].department_ids == [department.id]
    assert items[0].operation == operation.operation
    assert items[0].artifacts == [artifact.artifact]


async def test_round_trips_args_and_outputs(conn, redis_client):
    arg = await create_arg(conn, "tool-arg", "text", redis_client)
    arg_output = await create_args_output(
        conn,
        arg.id,
        "tool-arg-output",
        redis_client,
    )

    result = await create_tool(
        conn,
        "linked-tool-io",
        redis=redis_client,
        args_ids=[arg.id],
        args_output_ids=[arg_output.id],
    )

    items = await get_tools(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].args_ids == [arg.id]
    assert items[0].args_output_ids == [arg_output.id]
