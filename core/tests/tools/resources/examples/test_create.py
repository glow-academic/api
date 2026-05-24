"""Tests for create_example."""

import pytest

from app.tools.resources.examples.create import create_example
from app.tools.resources.examples.get import get_examples

pytestmark = pytest.mark.asyncio


async def test_creates_new_example(conn, redis_client):
    result = await create_example(conn, "test-example", redis_client)

    assert result.example == "test-example"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_example(conn, "test-example-visible", redis_client)

    items = await get_examples(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].example == "test-example-visible"


async def test_creates_second_row(conn, redis_client):
    first = await create_example(conn, "duplicate-example", redis_client)
    second = await create_example(conn, "duplicate-example", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_example(conn, "mcp-example", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
