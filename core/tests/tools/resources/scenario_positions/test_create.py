"""Tests for create_scenario_position."""

import pytest

from app.tools.resources.scenario_positions.create import (
    create_scenario_position,
)
from app.tools.resources.scenario_positions.get import get_scenario_positions
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def test_creates_new_scenario_position(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_position(conn, scenario.id, 1, redis_client)

    assert result.scenario_id == scenario.id
    assert result.value == 1
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_position(conn, scenario.id, 5, redis_client)

    items = await get_scenario_positions(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 5


async def test_creates_second_row(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    first = await create_scenario_position(conn, scenario.id, 1, redis_client)
    second = await create_scenario_position(conn, scenario.id, 1, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_position(
        conn, scenario.id, 10, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
