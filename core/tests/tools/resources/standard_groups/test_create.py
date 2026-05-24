"""Tests for create_standard_group."""

import pytest

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standard_groups.get import get_standard_groups

pytestmark = pytest.mark.asyncio


async def test_creates_new_standard_group(conn, redis_client):
    result = await create_standard_group(
        conn, "Test Group", "TG", "desc", 100, 70, redis_client
    )

    assert result.name == "Test Group"
    assert result.short_name == "TG"
    assert result.description == "desc"
    assert result.points == 100
    assert result.pass_points == 70
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_standard_group(
        conn, "Visible Group", "VG", "visible desc", 60, 40, redis_client
    )

    items = await get_standard_groups(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "Visible Group"


async def test_creates_second_row_for_same_params(conn, redis_client):
    first = await create_standard_group(
        conn, "Dup Group", "DG", "dup desc", 100, 70, redis_client
    )
    second = await create_standard_group(
        conn, "Dup Group", "DG", "dup desc", 100, 70, redis_client
    )

    assert first.id != second.id
    assert second.name == "Dup Group"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_standard_group(
        conn, "MCP Group", "MG", "mcp desc", 100, 70, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
