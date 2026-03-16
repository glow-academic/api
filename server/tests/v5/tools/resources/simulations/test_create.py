"""Tests for create_simulation."""

import pytest

from app.tools.resources.simulations.create import create_simulation
from app.tools.resources.simulations.get import get_simulations

pytestmark = pytest.mark.asyncio


async def test_creates_new_simulation(conn, redis_client):
    result = await create_simulation(
        conn, redis_client, name="test-sim", description="desc"
    )

    assert result.name == "test-sim"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_simulation(conn, redis_client, name="test-sim-visible")

    items = await get_simulations(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-sim-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_simulation(conn, redis_client, name="duplicate-sim")
    second = await create_simulation(conn, redis_client, name="duplicate-sim")

    assert first.id != second.id
    assert second.name == "duplicate-sim"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_simulation(conn, redis_client, name="mcp-sim", mcp=True)

    assert result.mcp is True
    assert result.generated is True
