"""Tests for search_slugs."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.slugs.create import create_slug
from app.tools.resources.slugs.search import search_slugs

pytestmark = pytest.mark.asyncio


async def test_finds_created_slug(conn, redis_client):
    await create_slug(conn, "search-test-alpha", redis_client)

    items = await search_slugs(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.value == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_slug(conn, "CaseTest-Slug", redis_client)

    items = await search_slugs(conn, redis_client, search="casetest-slug")

    assert any(i.value == "CaseTest-Slug" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_slugs(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_slug(conn, f"limit-slug-{unique_tag()}", redis_client)

    items = await search_slugs(conn, redis_client, search="limit-slug-", limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_slug(conn, f"offset-slug-{unique_tag()}", redis_client)

    all_items = await search_slugs(
        conn, redis_client, search="offset-slug-", limit_count=10
    )
    offset_items = await search_slugs(
        conn, redis_client, search="offset-slug-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_slug(conn, f"exclude-sa-{unique_tag()}", redis_client)
    b = await create_slug(conn, f"exclude-sb-{unique_tag()}", redis_client)

    items = await search_slugs(
        conn,
        redis_client,
        search="exclude-s",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_slugs(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_slug(conn, f"cache-hit-slug-{unique_tag()}", redis_client)

    items1 = await search_slugs(conn, redis_client, search="cache-hit-slug-")
    items2 = await search_slugs(conn, redis_client, search="cache-hit-slug-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_slug(conn, f"bypass-slug-{unique_tag()}", redis_client)

    items = await search_slugs(
        conn, redis_client, search="bypass-slug-", bypass_cache=True
    )

    assert len(items) >= 1
