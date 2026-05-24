"""Tests for search_scenario_time_limits."""

import pytest

from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)
from app.tools.resources.scenario_time_limits.search import (
    search_scenario_time_limits,
)
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def test_finds_created_scenario_time_limit(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    item = await create_scenario_time_limit(conn, scenario.id, 300, redis_client)

    items = await search_scenario_time_limits(conn, redis_client)

    assert len(items) >= 1
    assert any(i.id == item.id for i in items)


async def test_respects_limit(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    for i in range(5):
        await create_scenario_time_limit(conn, scenario.id, 100 + i, redis_client)

    items = await search_scenario_time_limits(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    for i in range(3):
        await create_scenario_time_limit(conn, scenario.id, 200 + i, redis_client)

    all_items = await search_scenario_time_limits(conn, redis_client, limit_count=100)
    offset_items = await search_scenario_time_limits(
        conn, redis_client, limit_count=100, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    a = await create_scenario_time_limit(conn, scenario.id, 301, redis_client)
    b = await create_scenario_time_limit(conn, scenario.id, 302, redis_client)

    items = await search_scenario_time_limits(conn, redis_client, exclude_ids=[a.id])

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_scenario_time_limits(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    await create_scenario_time_limit(conn, scenario.id, 500, redis_client)

    items1 = await search_scenario_time_limits(conn, redis_client)
    items2 = await search_scenario_time_limits(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    scenario = await create_scenario(conn, redis_client)
    await create_scenario_time_limit(conn, scenario.id, 600, redis_client)

    items = await search_scenario_time_limits(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
