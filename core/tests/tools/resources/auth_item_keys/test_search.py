"""Tests for search_auth_item_keys."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.auth_item_keys.create import create_auth_item_key
from app.tools.resources.auth_item_keys.search import search_auth_item_keys
from app.tools.resources.auths.create import create_auth
from app.tools.resources.items.create import create_item
from app.tools.resources.keys.create import create_key

pytestmark = pytest.mark.asyncio


async def _create_auth_item_key(conn, redis_client):
    """Helper to create an auth_item_key with required FKs."""
    auth = await create_auth(conn, redis_client, name=f"aik-auth-{unique_tag()}")
    item = await create_item(conn, f"aik-item-{unique_tag()}", "", redis_client)
    key = await create_key(conn, redis_client, name=f"aik-key-{unique_tag()}")
    return await create_auth_item_key(conn, auth.id, item.id, key.id, redis_client)


async def test_finds_created_auth_item_key(conn, redis_client):
    aik = await _create_auth_item_key(conn, redis_client)

    items = await search_auth_item_keys(conn, redis_client)

    assert len(items) >= 1
    assert any(i.id == aik.id for i in items)


async def test_respects_limit(conn, redis_client):
    for _ in range(3):
        await _create_auth_item_key(conn, redis_client)

    items = await search_auth_item_keys(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await _create_auth_item_key(conn, redis_client)
    b = await _create_auth_item_key(conn, redis_client)

    items = await search_auth_item_keys(
        conn,
        redis_client,
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_auth_item_keys(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_auth_item_key(conn, redis_client)

    items1 = await search_auth_item_keys(conn, redis_client)
    items2 = await search_auth_item_keys(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_auth_item_key(conn, redis_client)

    items = await search_auth_item_keys(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
