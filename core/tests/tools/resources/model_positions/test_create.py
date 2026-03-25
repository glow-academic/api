"""Tests for create_model_position."""

import pytest

from app.tools.resources.model_positions.create import create_model_position
from app.tools.resources.model_positions.get import get_model_positions
from app.tools.resources.models.create import create_model

pytestmark = pytest.mark.asyncio


async def test_creates_new_model_position(conn, redis_client):
    model = await create_model(conn, "test-model", redis=redis_client)
    result = await create_model_position(conn, model.id, 1, redis_client)

    assert result.model_id == model.id
    assert result.value == 1
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    model = await create_model(conn, "test-model-visible", redis=redis_client)
    result = await create_model_position(conn, model.id, 5, redis_client)

    items = await get_model_positions(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == 5


async def test_creates_second_row(conn, redis_client):
    model = await create_model(conn, "test-model-second", redis=redis_client)
    first = await create_model_position(conn, model.id, 1, redis_client)
    second = await create_model_position(conn, model.id, 1, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    model = await create_model(conn, "test-model-mcp", redis=redis_client)
    result = await create_model_position(conn, model.id, 10, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
