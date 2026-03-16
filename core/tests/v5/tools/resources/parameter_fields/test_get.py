"""Tests for get_parameter_fields."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.fields.create import create_field
from app.tools.resources.parameter_fields.get import get_parameter_fields

pytestmark = pytest.mark.asyncio


async def test_gets_created_parameter_field(conn, redis_client):
    field = await create_field(conn, "test-field", redis=redis_client)
    from app.tools.resources.parameter_fields.create import (
        create_parameter_field,
    )

    item = await create_parameter_field(conn, field.id, redis_client)

    items = await get_parameter_fields(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].field_id == field.id
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_parameter_fields(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_parameter_fields(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    field = await create_field(conn, "test-field-cache", redis=redis_client)
    from app.tools.resources.parameter_fields.create import (
        create_parameter_field,
    )

    item = await create_parameter_field(conn, field.id, redis_client)

    # First call populates cache
    items = await get_parameter_fields(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_parameter_fields(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    field = await create_field(conn, "test-field-bypass", redis=redis_client)
    from app.tools.resources.parameter_fields.create import (
        create_parameter_field,
    )

    item = await create_parameter_field(conn, field.id, redis_client)

    items = await get_parameter_fields(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/parameter_fields/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
