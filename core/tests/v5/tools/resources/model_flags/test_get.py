"""Tests for get_model_flags."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.flags.create import create_flag
from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.models.create import create_model

pytestmark = pytest.mark.asyncio


async def test_gets_created_model_flag(conn, redis_client):
    model = await create_model(conn, "test-model", redis=redis_client)
    flag = await create_flag(conn, "test-flag", "desc", "icon", redis_client)
    from app.tools.resources.model_flags.create import create_model_flag

    item = await create_model_flag(conn, model.id, flag.id, redis_client)

    items = await get_model_flags(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].model_id == model.id
    assert items[0].flag_id == flag.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_model_flags(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_model_flags(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    model = await create_model(conn, "test-model-cache", redis=redis_client)
    flag = await create_flag(conn, "test-flag-cache", "desc", "icon", redis_client)
    from app.tools.resources.model_flags.create import create_model_flag

    item = await create_model_flag(conn, model.id, flag.id, redis_client)

    # First call populates cache
    items = await get_model_flags(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_model_flags(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    model = await create_model(conn, "test-model-bypass", redis=redis_client)
    flag = await create_flag(conn, "test-flag-bypass", "desc", "icon", redis_client)
    from app.tools.resources.model_flags.create import create_model_flag

    item = await create_model_flag(conn, model.id, flag.id, redis_client)

    items = await get_model_flags(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/model_flags/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
