"""Tests for create_flag."""

import pytest

from app.tools.resources.flags.create import create_flag
from app.tools.resources.flags.get import get_flags

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_creates_new_flag(conn, redis_client):
    result = await create_flag(conn, "test-flag", "A flag", redis=redis_client)

    assert result.name == "test-flag"
    assert result.description == "A flag"
    assert result.icon is None
    assert result.type == "active"
    assert result.value is True
    assert result.active is True
    assert result.mcp is False


async def test_creates_flag_with_value_false(conn, redis_client):
    result = await create_flag(
            conn, "inactive-flag", "desc", redis=redis_client, value=False
    )

    assert result.value is False


async def test_visible_via_get(conn, redis_client):
    result = await create_flag(conn, "test-flag-visible", "desc", redis=redis_client)

    items = await get_flags(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_flag(conn, "duplicate-flag", "desc", redis=redis_client)
    second = await create_flag(conn, "duplicate-flag", "desc", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_flag(
            conn, "mcp-flag", "desc", redis=redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
