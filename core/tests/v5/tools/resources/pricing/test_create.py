"""Tests for create_pricing."""

import pytest

from app.tools.resources.pricing.create import create_pricing
from app.tools.resources.pricing.get import get_pricing

pytestmark = pytest.mark.asyncio


async def test_creates_new_pricing(conn, redis_client):
    result = await create_pricing(
        conn, "input", 0.5, "tokens", "tokens", 1000, redis_client
    )

    assert result.pricing_type == "input"
    assert result.price == pytest.approx(0.5)
    assert result.unit_name == "tokens"
    assert result.unit_category == "tokens"
    assert result.unit_value == 1000
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_pricing(
        conn, "output", 0.3, "chars", "tokens", 200, redis_client
    )

    items = await get_pricing(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].pricing_type == "output"


async def test_creates_second_row_for_same_params(conn, redis_client):
    first = await create_pricing(
        conn, "input", 0.5, "tokens", "tokens", 1000, redis_client
    )
    second = await create_pricing(
        conn, "input", 0.5, "tokens", "tokens", 1000, redis_client
    )

    assert first.id != second.id
    assert second.pricing_type == "input"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_pricing(
        conn, "input", 0.5, "tokens", "tokens", 1000, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
