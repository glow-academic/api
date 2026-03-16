"""Tests for get_simulation_availability."""

from datetime import UTC, datetime

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulations.create import create_simulation

pytestmark = pytest.mark.asyncio


async def test_gets_created_simulation_availability(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    item = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    items = await get_simulation_availability(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].simulation_id == simulation.id
    assert items[0].type == "start"
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_simulation_availability(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_simulation_availability(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    item = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    # First call populates cache
    items = await get_simulation_availability(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_simulation_availability(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    item = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    items = await get_simulation_availability(
        conn, [item.id], redis_client, bypass_cache=True
    )
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key(
        "/v5/resources/simulation_availability/get", {"ids": [str(item.id)]}
    )
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
