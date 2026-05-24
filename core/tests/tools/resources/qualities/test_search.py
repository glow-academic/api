"""Tests for search_qualities."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.qualities.create import create_quality
from app.tools.resources.qualities.search import search_qualities

pytestmark = pytest.mark.asyncio


async def test_finds_created_quality(conn, redis_client):
    await create_quality(conn, "high", redis_client)

    items = await search_qualities(conn, redis_client, search="high")

    assert len(items) >= 1
    assert any(i.quality == "high" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_quality(conn, "medium", redis_client)

    items = await search_qualities(conn, redis_client, search="MEDIUM")

    assert any(i.quality == "medium" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_qualities(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    await create_quality(conn, "low", redis_client)
    await create_quality(conn, "medium", redis_client)
    await create_quality(conn, "high", redis_client)

    items = await search_qualities(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    await create_quality(conn, "low", redis_client)
    await create_quality(conn, "medium", redis_client)
    await create_quality(conn, "high", redis_client)

    all_items = await search_qualities(conn, redis_client, limit_count=10)
    offset_items = await search_qualities(
        conn, redis_client, limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_quality(conn, "low", redis_client)
    b = await create_quality(conn, "high", redis_client)

    items = await search_qualities(
        conn,
        redis_client,
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_qualities(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_quality(conn, "high", redis_client)

    items1 = await search_qualities(conn, redis_client, search="high")
    items2 = await search_qualities(conn, redis_client, search="high")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_quality(conn, "low", redis_client)

    items = await search_qualities(conn, redis_client, search="low", bypass_cache=True)

    assert len(items) >= 1
