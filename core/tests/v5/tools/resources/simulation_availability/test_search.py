"""Tests for search_simulation_availability."""

from datetime import UTC, datetime

import pytest

from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_availability.search import (
    search_simulation_availability,
)
from app.tools.resources.simulations.create import create_simulation

pytestmark = pytest.mark.asyncio


async def test_finds_created_simulation_availability(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    item = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    items = await search_simulation_availability(conn, redis_client)

    assert len(items) >= 1
    assert any(i.id == item.id for i in items)


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        simulation = await create_simulation(conn, redis_client)
        now = datetime.now(UTC)
        await create_simulation_availability(
            conn, simulation.id, now, "start", redis_client
        )

    items = await search_simulation_availability(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        simulation = await create_simulation(conn, redis_client)
        now = datetime.now(UTC)
        await create_simulation_availability(
            conn, simulation.id, now, "start", redis_client
        )

    all_items = await search_simulation_availability(
        conn, redis_client, limit_count=100
    )
    offset_items = await search_simulation_availability(
        conn, redis_client, limit_count=100, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    sim_a = await create_simulation(conn, redis_client)
    sim_b = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    a = await create_simulation_availability(conn, sim_a.id, now, "start", redis_client)
    b = await create_simulation_availability(conn, sim_b.id, now, "start", redis_client)

    items = await search_simulation_availability(conn, redis_client, exclude_ids=[a.id])

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_simulation_availability(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    items1 = await search_simulation_availability(conn, redis_client)
    items2 = await search_simulation_availability(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    items = await search_simulation_availability(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
