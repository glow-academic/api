"""Tests for search_rubrics."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.rubrics.search import search_rubrics

pytestmark = pytest.mark.asyncio


async def test_finds_created_rubric(conn, redis_client):
    await create_rubric(conn, redis_client, name="search-test-alpha")

    items = await search_rubrics(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_rubric(conn, redis_client, name="CaseTest-Rubric")

    items = await search_rubrics(conn, redis_client, search="casetest-rubric")

    assert any(i.name == "CaseTest-Rubric" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_rubrics(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_rubric(conn, redis_client, name=f"limit-test-{unique_tag()}")

    items = await search_rubrics(
        conn, redis_client, search="limit-test-", limit_count=2
    )

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await create_rubric(conn, redis_client, name=f"exclude-a-{unique_tag()}")
    b = await create_rubric(conn, redis_client, name=f"exclude-b-{unique_tag()}")

    items = await search_rubrics(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_rubrics(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_rubric(conn, redis_client, name=f"cache-hit-{unique_tag()}")

    items1 = await search_rubrics(conn, redis_client, search="cache-hit-")
    items2 = await search_rubrics(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_rubric(conn, redis_client, name=f"bypass-{unique_tag()}")

    items = await search_rubrics(
        conn, redis_client, search="bypass-", bypass_cache=True
    )

    assert len(items) >= 1
