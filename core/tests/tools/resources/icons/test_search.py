"""Tests for search_icons."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.icons.create import create_icon
from app.tools.resources.icons.search import search_icons

pytestmark = pytest.mark.asyncio


async def test_finds_created_icon(conn, redis_client):
    await create_icon(conn, "search-test-alpha", "desc", "star", redis_client)

    items = await search_icons(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_icon(conn, "CaseTest-Icon", "desc", "circle", redis_client)

    items = await search_icons(conn, redis_client, search="casetest-icon")

    assert any(i.name == "CaseTest-Icon" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_icons(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_icon(
            conn, f"limit-icon-{unique_tag()}", "desc", "star", redis_client
        )

    items = await search_icons(conn, redis_client, search="limit-icon-", limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_icon(
            conn, f"offset-icon-{unique_tag()}", "desc", "star", redis_client
        )

    all_items = await search_icons(
        conn, redis_client, search="offset-icon-", limit_count=10
    )
    offset_items = await search_icons(
        conn, redis_client, search="offset-icon-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_icon(
        conn, f"exclude-icon-a-{unique_tag()}", "desc", "star", redis_client
    )
    b = await create_icon(
        conn, f"exclude-icon-b-{unique_tag()}", "desc", "star", redis_client
    )

    items = await search_icons(
        conn,
        redis_client,
        search="exclude-icon-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_icons(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_icon(
        conn, f"cache-hit-icon-{unique_tag()}", "desc", "star", redis_client
    )

    items1 = await search_icons(conn, redis_client, search="cache-hit-icon-")
    items2 = await search_icons(conn, redis_client, search="cache-hit-icon-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_icon(conn, f"bypass-icon-{unique_tag()}", "desc", "star", redis_client)

    items = await search_icons(
        conn, redis_client, search="bypass-icon-", bypass_cache=True
    )

    assert len(items) >= 1
