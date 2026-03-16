"""Tests for search_providers."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.providers.create import create_provider
from app.tools.resources.providers.search import search_providers

pytestmark = pytest.mark.asyncio


async def test_finds_created_provider(conn, redis_client):
    await create_provider(conn, name="search-test-alpha", redis=redis_client)

    items = await search_providers(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_provider(conn, name="CaseTest-Provider", redis=redis_client)

    items = await search_providers(conn, redis_client, search="casetest-provider")

    assert any(i.name == "CaseTest-Provider" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_providers(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_provider(
            conn, name=f"limit-test-{unique_tag()}", redis=redis_client
        )

    items = await search_providers(
        conn, redis_client, search="limit-test-", limit_count=2
    )

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await create_provider(
        conn, name=f"exclude-a-{unique_tag()}", redis=redis_client
    )
    b = await create_provider(
        conn, name=f"exclude-b-{unique_tag()}", redis=redis_client
    )

    items = await search_providers(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_providers(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_provider(conn, name=f"cache-hit-{unique_tag()}", redis=redis_client)

    items1 = await search_providers(conn, redis_client, search="cache-hit-")
    items2 = await search_providers(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_provider(conn, name=f"bypass-{unique_tag()}", redis=redis_client)

    items = await search_providers(
        conn, redis_client, search="bypass-", bypass_cache=True
    )

    assert len(items) >= 1
