"""Tests for search_fields."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.fields.create import create_field
from app.tools.resources.fields.search import search_fields

pytestmark = pytest.mark.asyncio


async def test_finds_created_field(conn, redis_client):
    await create_field(conn, "search-field-alpha", redis=redis_client)

    items = await search_fields(conn, redis_client, search="search-field-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-field-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_field(conn, "CaseTest-Field", redis=redis_client)

    items = await search_fields(conn, redis_client, search="casetest-field")

    assert any(i.name == "CaseTest-Field" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_fields(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_field(conn, f"limit-field-{unique_tag()}", redis=redis_client)

    items = await search_fields(
        conn, redis_client, search="limit-field-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_field(conn, f"offset-field-{unique_tag()}", redis=redis_client)

    all_items = await search_fields(
        conn, redis_client, search="offset-field-", limit_count=10
    )
    offset_items = await search_fields(
        conn, redis_client, search="offset-field-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_field(conn, f"exclude-fa-{unique_tag()}", redis=redis_client)
    b = await create_field(conn, f"exclude-fb-{unique_tag()}", redis=redis_client)

    items = await search_fields(
        conn,
        redis_client,
        search="exclude-f",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_fields(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_field(conn, f"cache-field-{unique_tag()}", redis=redis_client)

    items1 = await search_fields(conn, redis_client, search="cache-field-")
    items2 = await search_fields(conn, redis_client, search="cache-field-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_field(conn, f"bypass-field-{unique_tag()}", redis=redis_client)

    items = await search_fields(
        conn, redis_client, search="bypass-field-", bypass_cache=True
    )

    assert len(items) >= 1
