"""Tests for get_model_rubrics."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.models.create import create_model
from app.tools.resources.rubrics.create import create_rubric

pytestmark = pytest.mark.asyncio


async def test_gets_created_model_rubric(conn, redis_client):
    model = await create_model(conn, "test-model", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric")
    from app.tools.resources.model_rubrics.create import create_model_rubric

    item = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    items = await get_model_rubrics(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].model_id == model.id
    assert items[0].rubric_id == rubric.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_model_rubrics(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_model_rubrics(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    model = await create_model(conn, "test-model-cache", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric-cache")
    from app.tools.resources.model_rubrics.create import create_model_rubric

    item = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    # First call populates cache
    items = await get_model_rubrics(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_model_rubrics(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    model = await create_model(conn, "test-model-bypass", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric-bypass")
    from app.tools.resources.model_rubrics.create import create_model_rubric

    item = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    items = await get_model_rubrics(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/model_rubrics/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
