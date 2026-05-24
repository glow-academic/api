"""Tests for search_values."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.values.create import create_value
from app.tools.resources.values.search import search_values

pytestmark = pytest.mark.asyncio


async def test_finds_created_value(conn, redis_client):
    await create_value(conn, "search-test-alpha", redis_client)

    items = await search_values(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.value == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_value(conn, "CaseTest-Value", redis_client)

    items = await search_values(conn, redis_client, search="casetest-value")

    assert any(i.value == "CaseTest-Value" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_values(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_value(conn, f"limit-val-{unique_tag()}", redis_client)

    items = await search_values(conn, redis_client, search="limit-val-", limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_value(conn, f"offset-val-{unique_tag()}", redis_client)

    all_items = await search_values(
        conn, redis_client, search="offset-val-", limit_count=10
    )
    offset_items = await search_values(
        conn, redis_client, search="offset-val-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_value(conn, f"exclude-va-{unique_tag()}", redis_client)
    b = await create_value(conn, f"exclude-vb-{unique_tag()}", redis_client)

    items = await search_values(
        conn,
        redis_client,
        search="exclude-v",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_values(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_value(conn, f"cache-hit-val-{unique_tag()}", redis_client)

    items1 = await search_values(conn, redis_client, search="cache-hit-val-")
    items2 = await search_values(conn, redis_client, search="cache-hit-val-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_value(conn, f"bypass-val-{unique_tag()}", redis_client)

    items = await search_values(
        conn, redis_client, search="bypass-val-", bypass_cache=True
    )

    assert len(items) >= 1
