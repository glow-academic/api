"""Tests for create_scenario_time_limit."""

import pytest

from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)
from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def test_creates_new_scenario_time_limit(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_time_limit(conn, scenario.id, 300, redis_client)

    assert result.scenario_id == scenario.id
    assert result.time_limit_seconds == 300
    assert result.negative is False
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_time_limit(conn, scenario.id, 600, redis_client)

    items = await get_scenario_time_limits(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].time_limit_seconds == 600


async def test_creates_second_row(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    first = await create_scenario_time_limit(conn, scenario.id, 300, redis_client)
    second = await create_scenario_time_limit(conn, scenario.id, 300, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    result = await create_scenario_time_limit(
        conn, scenario.id, 900, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
