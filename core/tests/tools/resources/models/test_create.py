"""Tests for create_model."""

import pytest

from app.tools.resources.models.create import create_model
from app.tools.resources.models.get import get_models
from app.tools.resources.providers.create import create_provider

pytestmark = pytest.mark.asyncio


async def test_creates_new_model(conn, redis_client):
    result = await create_model(conn, "gpt-4", "test-model", "desc", redis_client)

    assert result.value == "gpt-4"
    assert result.name == "test-model"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_model(
        conn, "gpt-4-visible", "test-model-visible", redis=redis_client
    )

    items = await get_models(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == "gpt-4-visible"
    assert items[0].name == "test-model-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_model(conn, "gpt-4-dup", redis=redis_client)
    second = await create_model(conn, "gpt-4-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_model(conn, "gpt-4-mcp", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_round_trips_provider_link(conn, redis_client):
    provider = await create_provider(conn, "model-provider", redis=redis_client)

    result = await create_model(
        conn,
        "gpt-4-provider",
        redis=redis_client,
        provider_id=provider.id,
    )

    items = await get_models(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].provider_id == provider.id
