"""Tests for create_modality."""

import pytest

from app.tools.resources.modalities.create import create_modality
from app.tools.resources.modalities.get import get_modalities

pytestmark = pytest.mark.asyncio


async def test_creates_new_modality(conn, redis_client):
    result = await create_modality(conn, "text", redis_client)

    assert result.modality == "text"
    assert result.is_input is False
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_modality(conn, "image", redis_client, is_input=True)

    items = await get_modalities(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].modality == "image"
    assert items[0].is_input is True


async def test_creates_second_row_for_same_value(conn, redis_client):
    first = await create_modality(conn, "audio", redis_client)
    second = await create_modality(conn, "audio", redis_client)

    assert first.id != second.id
    assert second.modality == "audio"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_modality(conn, "video", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
