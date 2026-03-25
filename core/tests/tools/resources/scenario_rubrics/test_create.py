"""Tests for create_scenario_rubric."""

import pytest

from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_rubrics.get import get_scenario_rubrics
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def test_creates_new_scenario_rubric(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    rubric = await create_rubric(conn, redis_client)
    result = await create_scenario_rubric(conn, scenario.id, rubric.id, redis_client)

    assert result.scenario_id == scenario.id
    assert result.rubric_id == rubric.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    rubric = await create_rubric(conn, redis_client)
    result = await create_scenario_rubric(conn, scenario.id, rubric.id, redis_client)

    items = await get_scenario_rubrics(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].scenario_id == scenario.id
    assert items[0].rubric_id == rubric.id


async def test_creates_second_row(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    rubric = await create_rubric(conn, redis_client)
    first = await create_scenario_rubric(conn, scenario.id, rubric.id, redis_client)
    second = await create_scenario_rubric(conn, scenario.id, rubric.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    rubric = await create_rubric(conn, redis_client)
    result = await create_scenario_rubric(
        conn, scenario.id, rubric.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
