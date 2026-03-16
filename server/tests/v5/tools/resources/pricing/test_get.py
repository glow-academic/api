"""Tests for get_pricing."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.pricing.create import create_pricing
from app.tools.resources.pricing.get import get_pricing

pytestmark = pytest.mark.asyncio


async def test_gets_created_pricing(conn, redis_client):
    created = await create_pricing(
        conn, "input", 0.5, "tokens", "tokens", 1000, redis_client
    )

    items = await get_pricing(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].pricing_type == "input"
    assert items[0].price == pytest.approx(0.5)
    assert items[0].unit_name == "tokens"
    assert items[0].unit_category == "tokens"
    assert items[0].unit_value == 1000
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_pricing(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_pricing(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_pricing(
        conn, "output", 0.2, "tokens", "tokens", 500, redis_client
    )

    # First call populates cache
    items = await get_pricing(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_pricing(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].pricing_type == "output"
    assert items2[0].price == pytest.approx(0.2)


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_pricing(
        conn, "input", 1.0, "tokens", "tokens", 1000, redis_client
    )

    items = await get_pricing(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/pricing/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
