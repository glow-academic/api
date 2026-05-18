"""Tests for search_flags."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.flags.create import create_flag
from app.tools.resources.flags.search import search_flags

pytestmark = pytest.mark.asyncio


async def test_finds_created_flag(conn, redis_client):
    await create_flag(conn, "search-test-alpha", "desc", "home", redis_client)

    items = await search_flags(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_flag(conn, "CaseTest-Search-Flag", "desc", "home", redis_client)

    items = await search_flags(conn, redis_client, search="casetest-search-flag")

    assert any(i.name == "CaseTest-Search-Flag" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_flags(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_flag(
            conn, f"limit-test-flag-{unique_tag()}", "desc", "home", redis_client
        )

    items = await search_flags(
        conn, redis_client, search="limit-test-flag-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_flag(
            conn, f"offset-test-flag-{unique_tag()}", "desc", "home", redis_client
        )

    all_items = await search_flags(
        conn, redis_client, search="offset-test-flag-", limit_count=10
    )
    offset_items = await search_flags(
        conn, redis_client, search="offset-test-flag-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_flag(
        conn, f"exclude-a-flag-{unique_tag()}", "desc", "home", redis_client
    )
    b = await create_flag(
        conn, f"exclude-b-flag-{unique_tag()}", "desc", "home", redis_client
    )

    items = await search_flags(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_flags(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_flag(
        conn, f"cache-hit-flag-{unique_tag()}", "desc", "home", redis_client
    )

    items1 = await search_flags(conn, redis_client, search="cache-hit-flag-")
    items2 = await search_flags(conn, redis_client, search="cache-hit-flag-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_flag(conn, f"bypass-flag-{unique_tag()}", "desc", "home", redis_client)

    items = await search_flags(
        conn, redis_client, search="bypass-flag-", bypass_cache=True
    )

    assert len(items) >= 1
