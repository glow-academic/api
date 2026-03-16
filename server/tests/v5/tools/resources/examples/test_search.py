"""Tests for search_examples."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.examples.create import create_example
from app.tools.resources.examples.search import search_examples

pytestmark = pytest.mark.asyncio


async def test_finds_created_example(conn, redis_client):
    await create_example(conn, "search-test-example-alpha", redis_client)

    items = await search_examples(
        conn, redis_client, search="search-test-example-alpha"
    )

    assert len(items) >= 1
    assert any(i.example == "search-test-example-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_example(conn, "CaseTest-Search-Example", redis_client)

    items = await search_examples(conn, redis_client, search="casetest-search-example")

    assert any(i.example == "CaseTest-Search-Example" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_examples(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_example(conn, f"limit-test-example-{unique_tag()}", redis_client)

    items = await search_examples(
        conn, redis_client, search="limit-test-example-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_example(conn, f"offset-test-example-{unique_tag()}", redis_client)

    all_items = await search_examples(
        conn, redis_client, search="offset-test-example-", limit_count=10
    )
    offset_items = await search_examples(
        conn,
        redis_client,
        search="offset-test-example-",
        limit_count=10,
        offset_count=1,
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_example(conn, f"exclude-a-example-{unique_tag()}", redis_client)
    b = await create_example(conn, f"exclude-b-example-{unique_tag()}", redis_client)

    items = await search_examples(
        conn, redis_client, search="exclude-", exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_examples(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_example(conn, f"cache-hit-example-{unique_tag()}", redis_client)

    items1 = await search_examples(conn, redis_client, search="cache-hit-example-")
    items2 = await search_examples(conn, redis_client, search="cache-hit-example-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_example(conn, f"bypass-example-{unique_tag()}", redis_client)

    items = await search_examples(
        conn, redis_client, search="bypass-example-", bypass_cache=True
    )

    assert len(items) >= 1
