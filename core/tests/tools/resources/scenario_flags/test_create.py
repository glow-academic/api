"""Tests for create_scenario_flag."""

import pytest

from app.tools.resources.flags.create import create_flag
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def test_creates_new_scenario_flag(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    flag = await create_flag(conn, "test-flag", "desc", "icon", redis_client)
    result = await create_scenario_flag(conn, scenario.id, flag.id, redis_client)

    assert result.scenario_id == scenario.id
    assert result.flag_id == flag.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    flag = await create_flag(conn, "test-flag-visible", "desc", "icon", redis_client)
    result = await create_scenario_flag(conn, scenario.id, flag.id, redis_client)

    items = await get_scenario_flags(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].scenario_id == scenario.id
    assert items[0].flag_id == flag.id


async def test_creates_second_row(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    flag = await create_flag(conn, "test-flag-second", "desc", "icon", redis_client)
    first = await create_scenario_flag(conn, scenario.id, flag.id, redis_client)
    second = await create_scenario_flag(conn, scenario.id, flag.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    flag = await create_flag(conn, "test-flag-mcp", "desc", "icon", redis_client)
    result = await create_scenario_flag(
        conn, scenario.id, flag.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
