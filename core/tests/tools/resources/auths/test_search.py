"""Tests for search_auths."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.auths.create import create_auth
from app.tools.resources.auths.search import search_auths

pytestmark = pytest.mark.asyncio


async def test_finds_created_auth(conn, redis_client):
    await create_auth(conn, redis_client, name="search-test-alpha")

    items = await search_auths(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_auth(conn, redis_client, name="CaseTest-AuthSearch")

    items = await search_auths(conn, redis_client, search="casetest-authsearch")

    assert any(i.name == "CaseTest-AuthSearch" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_auths(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_auth(conn, redis_client, name=f"limit-test-auth-{unique_tag()}")

    items = await search_auths(
        conn, redis_client, search="limit-test-auth-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_auth(conn, redis_client, name=f"offset-test-auth-{unique_tag()}")

    all_items = await search_auths(
        conn, redis_client, search="offset-test-auth-", limit_count=10
    )
    offset_items = await search_auths(
        conn, redis_client, search="offset-test-auth-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_auth(conn, redis_client, name=f"exclude-a-auth-{unique_tag()}")
    b = await create_auth(conn, redis_client, name=f"exclude-b-auth-{unique_tag()}")

    items = await search_auths(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_auths(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_auth(conn, redis_client, name=f"cache-hit-auth-{unique_tag()}")

    items1 = await search_auths(conn, redis_client, search="cache-hit-auth-")
    items2 = await search_auths(conn, redis_client, search="cache-hit-auth-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_auth(conn, redis_client, name=f"bypass-auth-{unique_tag()}")

    items = await search_auths(
        conn, redis_client, search="bypass-auth-", bypass_cache=True
    )

    assert len(items) >= 1
