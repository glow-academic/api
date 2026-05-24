"""Tests for search_endpoints."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.endpoints.create import create_endpoint
from app.tools.resources.endpoints.search import search_endpoints

pytestmark = pytest.mark.asyncio


async def test_finds_created_endpoint(conn, redis_client):
    url = f"https://search-test-alpha-{unique_tag()}.example.com"
    await create_endpoint(conn, url, redis_client)

    items = await search_endpoints(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.base_url == url for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    url = f"https://CaseTest-Search-Endpoint-{unique_tag()}.example.com"
    await create_endpoint(conn, url, redis_client)

    items = await search_endpoints(
        conn, redis_client, search="casetest-search-endpoint"
    )

    assert any(i.base_url == url for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_endpoints(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_endpoint(
            conn,
            f"https://limit-test-endpoint-{unique_tag()}.example.com",
            redis_client,
        )

    items = await search_endpoints(
        conn, redis_client, search="limit-test-endpoint-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_endpoint(
            conn,
            f"https://offset-test-endpoint-{unique_tag()}.example.com",
            redis_client,
        )

    all_items = await search_endpoints(
        conn, redis_client, search="offset-test-endpoint-", limit_count=10
    )
    offset_items = await search_endpoints(
        conn,
        redis_client,
        search="offset-test-endpoint-",
        limit_count=10,
        offset_count=1,
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_endpoint(
        conn, f"https://exclude-a-endpoint-{unique_tag()}.example.com", redis_client
    )
    b = await create_endpoint(
        conn, f"https://exclude-b-endpoint-{unique_tag()}.example.com", redis_client
    )

    items = await search_endpoints(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_endpoints(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_endpoint(
        conn, f"https://cache-hit-endpoint-{unique_tag()}.example.com", redis_client
    )

    items1 = await search_endpoints(conn, redis_client, search="cache-hit-endpoint-")
    items2 = await search_endpoints(conn, redis_client, search="cache-hit-endpoint-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_endpoint(
        conn, f"https://bypass-endpoint-{unique_tag()}.example.com", redis_client
    )

    items = await search_endpoints(
        conn, redis_client, search="bypass-endpoint-", bypass_cache=True
    )

    assert len(items) >= 1
