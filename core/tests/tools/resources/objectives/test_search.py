"""Tests for search_objectives."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.objectives.create import create_objective
from app.tools.resources.objectives.search import search_objectives

pytestmark = pytest.mark.asyncio


async def test_finds_created_objective(conn, redis_client):
    await create_objective(conn, "search-test-obj-alpha", redis_client)

    items = await search_objectives(conn, redis_client, search="search-test-obj-alpha")

    assert len(items) >= 1
    assert any(i.objective == "search-test-obj-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_objective(conn, "CaseTest-Search-Obj", redis_client)

    items = await search_objectives(conn, redis_client, search="casetest-search-obj")

    assert any(i.objective == "CaseTest-Search-Obj" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_objectives(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_objective(conn, f"limit-test-obj-{unique_tag()}", redis_client)

    items = await search_objectives(
        conn, redis_client, search="limit-test-obj-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_objective(conn, f"offset-test-obj-{unique_tag()}", redis_client)

    all_items = await search_objectives(
        conn, redis_client, search="offset-test-obj-", limit_count=10
    )
    offset_items = await search_objectives(
        conn, redis_client, search="offset-test-obj-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_objective(conn, f"exclude-a-obj-{unique_tag()}", redis_client)
    b = await create_objective(conn, f"exclude-b-obj-{unique_tag()}", redis_client)

    items = await search_objectives(
        conn, redis_client, search="exclude-", exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_objectives(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_objective(conn, f"cache-hit-obj-{unique_tag()}", redis_client)

    items1 = await search_objectives(conn, redis_client, search="cache-hit-obj-")
    items2 = await search_objectives(conn, redis_client, search="cache-hit-obj-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_objective(conn, f"bypass-obj-{unique_tag()}", redis_client)

    items = await search_objectives(
        conn, redis_client, search="bypass-obj-", bypass_cache=True
    )

    assert len(items) >= 1
