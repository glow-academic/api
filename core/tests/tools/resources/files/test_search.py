"""Tests for search_files."""

import pytest

from app.tools.resources.files.create import create_file
from app.tools.resources.files.search import search_files

pytestmark = pytest.mark.asyncio


async def test_finds_created_file(conn, redis_client):
    f = await create_file(conn, redis_client)

    items = await search_files(conn, redis_client)

    ids = [i.id for i in items]
    assert f.id in ids


async def test_respects_limit(conn, redis_client):
    for _ in range(5):
        await create_file(conn, redis_client)

    items = await search_files(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    created = []
    for _ in range(3):
        f = await create_file(conn, redis_client)
        created.append(f)

    all_items = await search_files(conn, redis_client, limit_count=100)
    offset_items = await search_files(
        conn, redis_client, limit_count=100, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_file(conn, redis_client)
    b = await create_file(conn, redis_client)

    items = await search_files(conn, redis_client, exclude_ids=[a.id])

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_files(conn, redis_client, limit_count=0)

    assert items == []


async def test_bypass_cache(conn, redis_client):
    f = await create_file(conn, redis_client)

    items = await search_files(conn, redis_client, bypass_cache=True)

    ids = [i.id for i in items]
    assert f.id in ids
