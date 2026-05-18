"""Tests for search_scenario_flags."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.flags.create import create_flag
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_flags.search import search_scenario_flags
from app.tools.resources.scenarios.create import create_scenario

pytestmark = pytest.mark.asyncio


async def _create_scenario_flag_with_deps(conn, redis_client, flag_name: str):
    """Helper: create a scenario + flag + scenario_flag."""
    scenario = await create_scenario(
        conn, redis_client, name=f"scenario-{unique_tag()}"
    )
    flag = await create_flag(
        conn, name=flag_name, description="", icon="", redis=redis_client
    )
    sf = await create_scenario_flag(conn, scenario.id, flag.id, redis_client)
    return sf


async def test_finds_created_scenario_flag(conn, redis_client):
    await _create_scenario_flag_with_deps(conn, redis_client, "search-test-alpha")

    items = await search_scenario_flags(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_scenario_flags(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(3):
        await _create_scenario_flag_with_deps(
            conn, redis_client, f"limit-test-{unique_tag()}"
        )

    items = await search_scenario_flags(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    unique = unique_tag()
    a = await _create_scenario_flag_with_deps(conn, redis_client, f"exclude-a-{unique}")
    b = await _create_scenario_flag_with_deps(conn, redis_client, f"exclude-b-{unique}")

    items = await search_scenario_flags(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_scenario_flags(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_scenario_flag_with_deps(
        conn, redis_client, f"cache-hit-{unique_tag()}"
    )

    items1 = await search_scenario_flags(conn, redis_client)
    items2 = await search_scenario_flags(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_scenario_flag_with_deps(conn, redis_client, f"bypass-{unique_tag()}")

    items = await search_scenario_flags(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
