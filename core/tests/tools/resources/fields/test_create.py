"""Tests for create_field."""

import pytest

from app.tools.resources.fields.create import create_field
from app.tools.resources.fields.get import get_fields

pytestmark = pytest.mark.asyncio


async def test_creates_new_field(conn, redis_client):
    result = await create_field(conn, "test-field", "desc", redis_client)

    assert result.name == "test-field"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_field(conn, "test-field-visible", redis=redis_client)

    items = await get_fields(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-field-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_field(conn, "test-field-dup", redis=redis_client)
    second = await create_field(conn, "test-field-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_field(conn, "mcp-field", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
