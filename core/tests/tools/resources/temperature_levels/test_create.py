"""Tests for create_temperature_level."""

import pytest

from app.tools.resources.temperature_levels.create import (
    create_temperature_level,
)
from app.tools.resources.temperature_levels.get import get_temperature_levels

pytestmark = pytest.mark.asyncio


async def test_creates_new_temperature_level(conn, redis_client):
    result = await create_temperature_level(conn, 0.7, redis_client)

    assert result.temperature == pytest.approx(0.7)
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_temperature_level(conn, 0.3, redis_client)

    items = await get_temperature_levels(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].temperature == pytest.approx(0.3)


async def test_creates_second_row_for_same_value(conn, redis_client):
    first = await create_temperature_level(conn, 0.5, redis_client)
    second = await create_temperature_level(conn, 0.5, redis_client)

    assert first.id != second.id
    assert second.temperature == pytest.approx(0.5)


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_temperature_level(conn, 1.0, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
