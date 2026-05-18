"""Tests for search_scenario_rubrics."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_rubrics.search import (
    search_scenario_rubrics,
)
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def _create_scenario_rubric_with_deps(conn, redis_client):
    """Helper: create a scenario + rubric + scenario_rubric."""
    scenario = await create_scenario(
        conn, redis_client, name=f"scenario-{unique_tag()}"
    )
    rubric = await create_rubric(conn, redis_client, name=f"rubric-{unique_tag()}")
    sr = await create_scenario_rubric(conn, scenario.id, rubric.id, redis_client)
    return sr


async def test_finds_created_scenario_rubric(conn, redis_client):
    sr = await _create_scenario_rubric_with_deps(conn, redis_client)

    items = await search_scenario_rubrics(conn, redis_client, limit_count=1000)

    ids = [i.id for i in items]
    assert sr.id in ids


async def test_respects_limit(conn, redis_client):
    for _ in range(3):
        await _create_scenario_rubric_with_deps(conn, redis_client)

    items = await search_scenario_rubrics(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for _ in range(3):
        await _create_scenario_rubric_with_deps(conn, redis_client)

    all_items = await search_scenario_rubrics(conn, redis_client, limit_count=1000)
    offset_items = await search_scenario_rubrics(
        conn, redis_client, limit_count=1000, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await _create_scenario_rubric_with_deps(conn, redis_client)
    b = await _create_scenario_rubric_with_deps(conn, redis_client)

    items = await search_scenario_rubrics(
        conn, redis_client, limit_count=1000, exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_scenario_rubrics(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_scenario_rubric_with_deps(conn, redis_client)

    items1 = await search_scenario_rubrics(conn, redis_client, limit_count=1000)
    items2 = await search_scenario_rubrics(conn, redis_client, limit_count=1000)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_scenario_rubric_with_deps(conn, redis_client)

    items = await search_scenario_rubrics(
        conn, redis_client, limit_count=1000, bypass_cache=True
    )

    assert len(items) >= 1
