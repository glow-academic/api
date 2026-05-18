"""Tests for create_model_rubric."""

import pytest

from app.tools.resources.model_rubrics.create import create_model_rubric
from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.models.create import create_model
from app.tools.resources.rubrics.create import create_rubric

pytestmark = pytest.mark.asyncio


async def test_creates_new_model_rubric(conn, redis_client):
    model = await create_model(conn, "test-model", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric")
    result = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    assert result.model_id == model.id
    assert result.rubric_id == rubric.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    model = await create_model(conn, "test-model-visible", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric-visible")
    result = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    items = await get_model_rubrics(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].model_id == model.id
    assert items[0].rubric_id == rubric.id


async def test_creates_second_row(conn, redis_client):
    model = await create_model(conn, "test-model-second", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric-second")
    first = await create_model_rubric(conn, model.id, rubric.id, redis_client)
    second = await create_model_rubric(conn, model.id, rubric.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    model = await create_model(conn, "test-model-mcp", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name="test-rubric-mcp")
    result = await create_model_rubric(
        conn, model.id, rubric.id, redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
