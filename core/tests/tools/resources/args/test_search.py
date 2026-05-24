"""Tests for search_args."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.args.create import create_arg
from app.tools.resources.args.search import search_args

pytestmark = pytest.mark.asyncio


async def test_finds_created_arg(conn, redis_client):
    await create_arg(conn, "search-test-alpha", "string", redis_client)

    items = await search_args(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_arg(conn, "CaseTest-Arg", "string", redis_client)

    items = await search_args(conn, redis_client, search="casetest-arg")

    assert any(i.name == "CaseTest-Arg" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_args(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_arg(conn, f"limit-arg-{unique_tag()}", "string", redis_client)

    items = await search_args(conn, redis_client, search="limit-arg-", limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_arg(conn, f"offset-arg-{unique_tag()}", "string", redis_client)

    all_items = await search_args(
        conn, redis_client, search="offset-arg-", limit_count=10
    )
    offset_items = await search_args(
        conn, redis_client, search="offset-arg-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_arg(conn, f"exclude-aa-{unique_tag()}", "string", redis_client)
    b = await create_arg(conn, f"exclude-ab-{unique_tag()}", "string", redis_client)

    items = await search_args(
        conn,
        redis_client,
        search="exclude-a",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_args(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_arg(conn, f"cache-hit-arg-{unique_tag()}", "string", redis_client)

    items1 = await search_args(conn, redis_client, search="cache-hit-arg-")
    items2 = await search_args(conn, redis_client, search="cache-hit-arg-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_arg(conn, f"bypass-arg-{unique_tag()}", "string", redis_client)

    items = await search_args(
        conn, redis_client, search="bypass-arg-", bypass_cache=True
    )

    assert len(items) >= 1
