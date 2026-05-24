"""Tests for create_parameter_field."""

import pytest

from app.tools.resources.fields.create import create_field
from app.tools.resources.parameter_fields.create import create_parameter_field
from app.tools.resources.parameter_fields.get import get_parameter_fields

pytestmark = pytest.mark.asyncio


async def test_creates_new_parameter_field(conn, redis_client):
    field = await create_field(conn, "test-field", redis=redis_client)
    result = await create_parameter_field(conn, field.id, redis_client)

    assert result.field_id == field.id
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    field = await create_field(conn, "test-field-visible", redis=redis_client)
    result = await create_parameter_field(conn, field.id, redis_client)

    items = await get_parameter_fields(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].field_id == field.id


async def test_creates_second_row(conn, redis_client):
    field = await create_field(conn, "test-field-second", redis=redis_client)
    first = await create_parameter_field(conn, field.id, redis_client)
    second = await create_parameter_field(conn, field.id, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    field = await create_field(conn, "test-field-mcp", redis=redis_client)
    result = await create_parameter_field(conn, field.id, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
