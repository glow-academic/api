"""Tests for create_scenario."""

import pytest

from app.tools.resources.scenarios.create import create_scenario
from app.tools.resources.scenarios.get import get_scenarios

pytestmark = pytest.mark.asyncio


async def test_creates_new_scenario(conn, redis_client):
    result = await create_scenario(
        conn, redis_client, name="test-scenario", description="desc"
    )

    assert result.name == "test-scenario"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_scenario(conn, redis_client, name="test-scenario-visible")

    items = await get_scenarios(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-scenario-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_scenario(conn, redis_client, name="duplicate-scenario")
    second = await create_scenario(conn, redis_client, name="duplicate-scenario")

    assert first.id != second.id
    assert second.name == "duplicate-scenario"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_scenario(conn, redis_client, name="mcp-scenario", mcp=True)

    assert result.mcp is True
    assert result.generated is True
