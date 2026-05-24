"""Tests for create_simulation_availability."""

from datetime import UTC, datetime

import pytest

from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulations.create import create_simulation

pytestmark = pytest.mark.asyncio


async def test_creates_new_simulation_availability(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    result = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    assert result.simulation_id == simulation.id
    assert result.type == "start"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    result = await create_simulation_availability(
        conn, simulation.id, now, "end", redis_client
    )

    items = await get_simulation_availability(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].type == "end"


async def test_returns_existing_on_conflict(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    first = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )
    second = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client
    )

    assert first.id == second.id


async def test_sets_mcp_flag(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    now = datetime.now(UTC)
    result = await create_simulation_availability(
        conn, simulation.id, now, "start", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
