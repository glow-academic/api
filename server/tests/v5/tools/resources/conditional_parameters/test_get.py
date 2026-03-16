"""Tests for get_conditional_parameters."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.conditional_parameters.get import (
    get_conditional_parameters,
)
from app.tools.resources.parameters.create import create_parameter

pytestmark = pytest.mark.asyncio


async def test_gets_created_conditional_parameter(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param")
    from app.tools.resources.conditional_parameters.create import (
        create_conditional_parameter,
    )

    item = await create_conditional_parameter(conn, param.id, redis_client)

    items = await get_conditional_parameters(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].parameter_id == param.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_conditional_parameters(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_conditional_parameters(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param-cache")
    from app.tools.resources.conditional_parameters.create import (
        create_conditional_parameter,
    )

    item = await create_conditional_parameter(conn, param.id, redis_client)

    # First call populates cache
    items = await get_conditional_parameters(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_conditional_parameters(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    param = await create_parameter(conn, redis_client, name="test-param-bypass")
    from app.tools.resources.conditional_parameters.create import (
        create_conditional_parameter,
    )

    item = await create_conditional_parameter(conn, param.id, redis_client)

    items = await get_conditional_parameters(
        conn, [item.id], redis_client, bypass_cache=True
    )
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key(
        "/v5/resources/conditional_parameters/get", {"ids": [str(item.id)]}
    )
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
