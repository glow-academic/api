"""Tests for search_options."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.options.create import create_option
from app.tools.resources.options.search import search_options

pytestmark = pytest.mark.asyncio


async def test_finds_created_option(conn, redis_client):
    await create_option(conn, f"search-test-{unique_tag()}", redis_client)

    items = await search_options(conn, redis_client, search="search-test-")

    assert len(items) >= 1


async def test_search_is_case_insensitive(conn, redis_client):
    await create_option(conn, "CaseTest-Option", redis_client)

    items = await search_options(conn, redis_client, search="casetest-option")

    assert any(i.option_text == "CaseTest-Option" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_options(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_option(conn, f"limit-test-{unique_tag()}", redis_client)

    items = await search_options(
        conn, redis_client, search="limit-test-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_option(conn, f"offset-test-{unique_tag()}", redis_client)

    all_items = await search_options(
        conn, redis_client, search="offset-test-", limit_count=10
    )
    offset_items = await search_options(
        conn, redis_client, search="offset-test-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_option(conn, f"exclude-a-{unique_tag()}", redis_client)
    b = await create_option(conn, f"exclude-b-{unique_tag()}", redis_client)

    items = await search_options(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_options(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_option(conn, f"cache-hit-{unique_tag()}", redis_client)

    items1 = await search_options(conn, redis_client, search="cache-hit-")
    items2 = await search_options(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_option(conn, f"bypass-{unique_tag()}", redis_client)

    items = await search_options(
        conn, redis_client, search="bypass-", bypass_cache=True
    )

    assert len(items) >= 1
