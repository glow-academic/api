"""Tests for create_standard."""

import pytest

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standards.create import create_standard
from app.tools.resources.standards.get import get_standards

pytestmark = pytest.mark.asyncio


async def test_creates_new_standard(conn, redis_client):
    sg = await create_standard_group(conn, "group", "sg", "desc", 10, 5, redis_client)
    result = await create_standard(
        conn, "Test Standard", "desc", 10, sg.id, redis_client
    )

    assert result.name == "Test Standard"
    assert result.description == "desc"
    assert result.points == 10
    assert result.standard_group_id == sg.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    sg = await create_standard_group(
        conn, "group-visible", "sgv", "desc", 10, 5, redis_client
    )
    result = await create_standard(
        conn, "Visible Standard", "desc", 5, sg.id, redis_client
    )

    items = await get_standards(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "Visible Standard"


async def test_creates_second_row(conn, redis_client):
    sg = await create_standard_group(
        conn, "group-second", "sgs", "desc", 10, 5, redis_client
    )
    first = await create_standard(conn, "Standard A", "desc", 10, sg.id, redis_client)
    second = await create_standard(conn, "Standard B", "desc", 10, sg.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    sg = await create_standard_group(
        conn, "group-mcp", "sgm", "desc", 10, 5, redis_client
    )
    result = await create_standard(
        conn, "MCP Standard", "desc", 10, sg.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
