"""Tests for create_conditional_parameter."""

import pytest

from app.tools.resources.conditional_parameters.create import (
    create_conditional_parameter,
)
from app.tools.resources.conditional_parameters.get import (
    get_conditional_parameters,
)
from app.tools.resources.parameters.create import create_parameter

pytestmark = pytest.mark.asyncio


async def test_creates_new_conditional_parameter(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param")
    result = await create_conditional_parameter(conn, param.id, redis_client)

    assert result.parameter_id == param.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param-visible")
    result = await create_conditional_parameter(conn, param.id, redis_client)

    items = await get_conditional_parameters(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].parameter_id == param.id


async def test_creates_second_row(conn, redis_client):
    param1 = await create_parameter(conn, redis_client, name="test-param-first")
    param2 = await create_parameter(conn, redis_client, name="test-param-second")
    first = await create_conditional_parameter(conn, param1.id, redis_client)
    second = await create_conditional_parameter(conn, param2.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param-mcp")
    result = await create_conditional_parameter(conn, param.id, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
