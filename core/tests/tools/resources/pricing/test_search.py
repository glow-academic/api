"""Tests for search_pricing."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.pricing.create import create_pricing
from app.tools.resources.pricing.search import search_pricing

pytestmark = pytest.mark.asyncio


async def test_finds_created_pricing(conn, redis_client):
    await create_pricing(conn, "input", 0.01, "tokens", "tokens", 1000, redis_client)

    items = await search_pricing(conn, redis_client, search="input")

    assert len(items) >= 1


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_pricing(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    items = await search_pricing(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await create_pricing(conn, "input", 0.02, "tokens", "tokens", 500, redis_client)

    items = await search_pricing(
        conn,
        redis_client,
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_pricing(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_pricing(conn, "input", 0.03, "tokens", "tokens", 100, redis_client)

    items1 = await search_pricing(conn, redis_client, search="input")
    items2 = await search_pricing(conn, redis_client, search="input")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_pricing(conn, "input", 0.04, "tokens", "tokens", 200, redis_client)

    items = await search_pricing(conn, redis_client, search="input", bypass_cache=True)

    assert len(items) >= 1
