"""Tests for search_items."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.items.create import create_item
from app.tools.resources.items.search import search_items

pytestmark = pytest.mark.asyncio


async def test_finds_created_item(conn, redis_client):
    await create_item(conn, "search-test-alpha", "desc", redis_client)

    items = await search_items(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_item(conn, "CaseTest-Search-Item", "desc", redis_client)

    items = await search_items(conn, redis_client, search="casetest-search-item")

    assert any(i.name == "CaseTest-Search-Item" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_items(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_item(conn, f"limit-test-item-{unique_tag()}", "desc", redis_client)

    items = await search_items(
        conn, redis_client, search="limit-test-item-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_item(
            conn, f"offset-test-item-{unique_tag()}", "desc", redis_client
        )

    all_items = await search_items(
        conn, redis_client, search="offset-test-item-", limit_count=10
    )
    offset_items = await search_items(
        conn, redis_client, search="offset-test-item-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_item(conn, f"exclude-a-item-{unique_tag()}", "desc", redis_client)
    b = await create_item(conn, f"exclude-b-item-{unique_tag()}", "desc", redis_client)

    items = await search_items(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_items(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_item(conn, f"cache-hit-item-{unique_tag()}", "desc", redis_client)

    items1 = await search_items(conn, redis_client, search="cache-hit-item-")
    items2 = await search_items(conn, redis_client, search="cache-hit-item-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_item(conn, f"bypass-item-{unique_tag()}", "desc", redis_client)

    items = await search_items(
        conn, redis_client, search="bypass-item-", bypass_cache=True
    )

    assert len(items) >= 1
