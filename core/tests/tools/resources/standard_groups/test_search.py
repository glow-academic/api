"""Tests for search_standard_groups."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standard_groups.search import search_standard_groups

pytestmark = pytest.mark.asyncio


async def test_finds_created_standard_group(conn, redis_client):
    await create_standard_group(
        conn, "search-test-alpha", "STA", "desc", 100, 70, redis_client
    )

    items = await search_standard_groups(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_standard_group(
        conn, "CaseTest-Search-SG", "CTS", "desc", 100, 70, redis_client
    )

    items = await search_standard_groups(
        conn, redis_client, search="casetest-search-sg"
    )

    assert any(i.name == "CaseTest-Search-SG" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_standard_groups(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_standard_group(
            conn, f"limit-test-sg-{unique_tag()}", "LT", "desc", 100, 70, redis_client
        )

    items = await search_standard_groups(
        conn, redis_client, search="limit-test-sg-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_standard_group(
            conn, f"offset-test-sg-{unique_tag()}", "OT", "desc", 100, 70, redis_client
        )

    all_items = await search_standard_groups(
        conn, redis_client, search="offset-test-sg-", limit_count=10
    )
    offset_items = await search_standard_groups(
        conn, redis_client, search="offset-test-sg-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_standard_group(
        conn, f"exclude-a-sg-{unique_tag()}", "EA", "desc", 100, 70, redis_client
    )
    b = await create_standard_group(
        conn, f"exclude-b-sg-{unique_tag()}", "EB", "desc", 100, 70, redis_client
    )

    items = await search_standard_groups(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_standard_groups(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_standard_group(
        conn, f"cache-hit-sg-{unique_tag()}", "CH", "desc", 100, 70, redis_client
    )

    items1 = await search_standard_groups(conn, redis_client, search="cache-hit-sg-")
    items2 = await search_standard_groups(conn, redis_client, search="cache-hit-sg-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_standard_group(
        conn, f"bypass-sg-{unique_tag()}", "BP", "desc", 100, 70, redis_client
    )

    items = await search_standard_groups(
        conn, redis_client, search="bypass-sg-", bypass_cache=True
    )

    assert len(items) >= 1
