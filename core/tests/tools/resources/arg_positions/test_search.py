"""Tests for search_arg_positions."""

import pytest

from app.tools.resources.arg_positions.create import create_arg_position
from app.tools.resources.arg_positions.search import search_arg_positions
from app.tools.resources.args.create import create_arg

pytestmark = pytest.mark.asyncio


async def test_finds_created_arg_position(conn, redis_client):
    arg = await create_arg(conn, "search-ap-test", "text", redis_client)
    item = await create_arg_position(conn, arg.id, 1, redis_client)

    items = await search_arg_positions(
        conn, redis_client, limit_count=500, bypass_cache=True
    )

    assert len(items) >= 1
    assert any(i.id == item.id for i in items)


async def test_respects_limit(conn, redis_client):
    arg = await create_arg(conn, "search-ap-limit", "text", redis_client)
    for i in range(5):
        await create_arg_position(conn, arg.id, 100 + i, redis_client)

    items = await search_arg_positions(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    arg = await create_arg(conn, "search-ap-offset", "text", redis_client)
    for i in range(3):
        await create_arg_position(conn, arg.id, 200 + i, redis_client)

    all_items = await search_arg_positions(conn, redis_client, limit_count=500)
    offset_items = await search_arg_positions(
        conn, redis_client, limit_count=500, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    arg = await create_arg(conn, "search-ap-exclude", "text", redis_client)
    a = await create_arg_position(conn, arg.id, 301, redis_client)
    b = await create_arg_position(conn, arg.id, 302, redis_client)

    items = await search_arg_positions(
        conn, redis_client, limit_count=500, exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_arg_positions(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    arg = await create_arg(conn, "search-ap-cache", "text", redis_client)
    await create_arg_position(conn, arg.id, 500, redis_client)

    items1 = await search_arg_positions(conn, redis_client, limit_count=500)
    items2 = await search_arg_positions(conn, redis_client, limit_count=500)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    arg = await create_arg(conn, "search-ap-bypass", "text", redis_client)
    await create_arg_position(conn, arg.id, 600, redis_client)

    items = await search_arg_positions(
        conn, redis_client, limit_count=500, bypass_cache=True
    )

    assert len(items) >= 1
