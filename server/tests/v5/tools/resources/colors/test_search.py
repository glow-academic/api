"""Tests for search_colors."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.colors.create import create_color
from app.tools.resources.colors.search import search_colors

pytestmark = pytest.mark.asyncio


async def test_finds_created_color(conn, redis_client):
    await create_color(conn, "search-test-red", "A red", "#FF0000", redis_client)

    items = await search_colors(conn, redis_client, search="search-test-red")

    assert len(items) >= 1
    assert any(i.name == "search-test-red" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_color(conn, "CaseTest-Color", "desc", "#00FF00", redis_client)

    items = await search_colors(conn, redis_client, search="casetest-color")

    assert any(i.name == "CaseTest-Color" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_colors(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_color(
            conn, f"limit-color-{unique_tag()}", "desc", "#AAAAAA", redis_client
        )

    items = await search_colors(
        conn, redis_client, search="limit-color-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_color(
            conn, f"offset-color-{unique_tag()}", "desc", "#BBBBBB", redis_client
        )

    all_items = await search_colors(
        conn, redis_client, search="offset-color-", limit_count=10
    )
    offset_items = await search_colors(
        conn, redis_client, search="offset-color-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_color(
        conn, f"exclude-a-{unique_tag()}", "desc", "#111111", redis_client
    )
    b = await create_color(
        conn, f"exclude-b-{unique_tag()}", "desc", "#222222", redis_client
    )

    items = await search_colors(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_colors(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_color(
        conn, f"cache-hit-{unique_tag()}", "desc", "#CCCCCC", redis_client
    )

    items1 = await search_colors(conn, redis_client, search="cache-hit-")
    items2 = await search_colors(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_color(conn, f"bypass-{unique_tag()}", "desc", "#DDDDDD", redis_client)

    items = await search_colors(conn, redis_client, search="bypass-", bypass_cache=True)

    assert len(items) >= 1
