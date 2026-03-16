"""Tests for create_model_flag."""

import pytest

from app.tools.resources.flags.create import create_flag
from app.tools.resources.model_flags.create import create_model_flag
from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.models.create import create_model

pytestmark = pytest.mark.asyncio


async def test_creates_new_model_flag(conn, redis_client):
    model = await create_model(conn, "test-model", redis=redis_client)
    flag = await create_flag(conn, "test-flag", "desc", "icon", redis_client)
    result = await create_model_flag(conn, model.id, flag.id, redis_client)

    assert result.model_id == model.id
    assert result.flag_id == flag.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    model = await create_model(conn, "test-model-visible", redis=redis_client)
    flag = await create_flag(conn, "test-flag-visible", "desc", "icon", redis_client)
    result = await create_model_flag(conn, model.id, flag.id, redis_client)

    items = await get_model_flags(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].model_id == model.id
    assert items[0].flag_id == flag.id


async def test_creates_second_row(conn, redis_client):
    model = await create_model(conn, "test-model-second", redis=redis_client)
    flag = await create_flag(conn, "test-flag-second", "desc", "icon", redis_client)
    first = await create_model_flag(conn, model.id, flag.id, redis_client)
    second = await create_model_flag(conn, model.id, flag.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    model = await create_model(conn, "test-model-mcp", redis=redis_client)
    flag = await create_flag(conn, "test-flag-mcp", "desc", "icon", redis_client)
    result = await create_model_flag(conn, model.id, flag.id, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
