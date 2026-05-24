"""Tests for create_simulation_position."""

import pytest

from app.tools.resources.simulation_positions.create import (
    create_simulation_position,
)
from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulations.create import create_simulation

pytestmark = pytest.mark.asyncio


async def test_creates_new_simulation_position(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    result = await create_simulation_position(conn, simulation.id, 1, redis_client)

    assert result.simulation_id == simulation.id
    assert result.value == 1
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    result = await create_simulation_position(conn, simulation.id, 5, redis_client)

    items = await get_simulation_positions(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 5


async def test_creates_second_row(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    first = await create_simulation_position(conn, simulation.id, 1, redis_client)
    second = await create_simulation_position(conn, simulation.id, 1, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    simulation = await create_simulation(conn, redis_client)
    result = await create_simulation_position(
        conn, simulation.id, 10, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
