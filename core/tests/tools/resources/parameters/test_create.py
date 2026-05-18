"""Tests for create_parameter."""

import pytest

from app.tools.resources.parameters.create import create_parameter
from app.tools.resources.parameters.get import get_parameters

pytestmark = pytest.mark.asyncio


async def test_creates_new_parameter(conn, redis_client):
    result = await create_parameter(
        conn, redis_client, name="test-param", description="desc"
    )

    assert result.name == "test-param"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_parameter(conn, redis_client, name="test-param-visible")

    items = await get_parameters(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-param-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_parameter(conn, redis_client, name="duplicate-param")
    second = await create_parameter(conn, redis_client, name="duplicate-param")

    assert first.id != second.id
    assert second.name == "duplicate-param"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_parameter(conn, redis_client, name="mcp-param", mcp=True)

    assert result.mcp is True
    assert result.generated is True
