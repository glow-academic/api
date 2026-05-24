"""Tests for search_provider_keys."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.keys.create import create_key
from app.tools.resources.provider_keys.create import create_provider_key
from app.tools.resources.provider_keys.search import search_provider_keys
from app.tools.resources.providers.create import create_provider

pytestmark = pytest.mark.asyncio


async def _create_provider_key(conn, redis_client, name_suffix=None):
    """Helper to create a provider_key with required FKs."""
    suffix = name_suffix or unique_tag()
    provider = await create_provider(conn, f"pk-prov-{suffix}", redis=redis_client)
    key = await create_key(conn, redis_client, name=f"pk-key-{suffix}")
    return await create_provider_key(
        conn,
        provider.id,
        key.id,
        redis_client,
        name=f"pk-name-{suffix}",
    )


async def test_finds_created_provider_key(conn, redis_client):
    pk = await _create_provider_key(conn, redis_client, name_suffix="search-test-pk")

    items = await search_provider_keys(
        conn, redis_client, search="pk-name-search-test-pk"
    )

    assert len(items) >= 1
    assert any(i.id == pk.id for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await _create_provider_key(conn, redis_client, name_suffix="CaseTestPk")

    items = await search_provider_keys(conn, redis_client, search="pk-name-casetestpk")

    assert any(i.name == "pk-name-CaseTestPk" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_provider_keys(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for _ in range(5):
        await _create_provider_key(conn, redis_client)

    items = await search_provider_keys(
        conn, redis_client, search="pk-name-", limit_count=2
    )

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await _create_provider_key(
        conn, redis_client, name_suffix=f"excl-a-{unique_tag()}"
    )
    b = await _create_provider_key(
        conn, redis_client, name_suffix=f"excl-b-{unique_tag()}"
    )

    items = await search_provider_keys(
        conn,
        redis_client,
        search="pk-name-excl-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_provider_keys(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_provider_key(conn, redis_client, name_suffix=f"cache-{unique_tag()}")

    items1 = await search_provider_keys(conn, redis_client, search="pk-name-cache-")
    items2 = await search_provider_keys(conn, redis_client, search="pk-name-cache-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_provider_key(conn, redis_client, name_suffix=f"bypass-{unique_tag()}")

    items = await search_provider_keys(
        conn, redis_client, search="pk-name-bypass-", bypass_cache=True
    )

    assert len(items) >= 1
