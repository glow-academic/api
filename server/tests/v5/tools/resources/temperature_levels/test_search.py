"""Tests for search_temperature_levels."""

import pytest

from app.tools.resources.temperature_levels.create import (
    create_temperature_level,
)
from app.tools.resources.temperature_levels.search import (
    search_temperature_levels,
)

pytestmark = pytest.mark.asyncio


async def test_finds_created_temperature_level(conn, redis_client):
    await create_temperature_level(conn, 0.5550, redis_client)

    items = await search_temperature_levels(conn, redis_client, search="0.555")

    assert len(items) >= 1


async def test_search_by_temperature_value(conn, redis_client):
    await create_temperature_level(conn, 0.777, redis_client)

    items = await search_temperature_levels(conn, redis_client, search="0.777")

    assert any(i.temperature == pytest.approx(0.777, abs=0.01) for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_temperature_levels(conn, redis_client, search="999.999")

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_temperature_level(conn, 0.4410 + i * 0.0001, redis_client)

    items = await search_temperature_levels(
        conn, redis_client, search="0.441", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_temperature_level(conn, 0.3310 + i * 0.0001, redis_client)

    all_items = await search_temperature_levels(
        conn, redis_client, search="0.331", limit_count=10
    )
    offset_items = await search_temperature_levels(
        conn, redis_client, search="0.331", limit_count=10, offset_count=1
    )

    assert len(all_items) >= 3
    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_temperature_level(conn, 0.111, redis_client)
    b = await create_temperature_level(conn, 0.112, redis_client)

    items = await search_temperature_levels(
        conn,
        redis_client,
        search="0.11",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_temperature_levels(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_temperature_level(conn, 0.888, redis_client)

    items1 = await search_temperature_levels(conn, redis_client, search="0.888")
    items2 = await search_temperature_levels(conn, redis_client, search="0.888")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_temperature_level(conn, 0.999, redis_client)

    items = await search_temperature_levels(
        conn, redis_client, search="0.999", bypass_cache=True
    )

    assert len(items) >= 1
