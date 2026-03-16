"""Tests for get_options."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.options.create import create_option
from app.tools.resources.options.get import get_options

pytestmark = pytest.mark.asyncio


async def test_gets_created_option(conn, redis_client):
    created = await create_option(conn, "option A", redis_client)

    items = await get_options(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].option_text == "option A"
    assert items[0].is_correct is False
    assert items[0].question_id is None
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_options(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_options(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_option(conn, "option B", redis_client)

    # First call populates cache
    items = await get_options(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_options(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].option_text == "option B"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_option(conn, "option C", redis_client)

    items = await get_options(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/options/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
