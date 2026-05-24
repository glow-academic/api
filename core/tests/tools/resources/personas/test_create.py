"""Tests for create_persona."""

import pytest

from app.tools.resources.personas.create import create_persona
from app.tools.resources.personas.get import get_personas

pytestmark = pytest.mark.asyncio


async def test_creates_new_persona(conn, redis_client):
    result = await create_persona(
        conn, redis_client, name="test-persona", description="desc"
    )

    assert result.name == "test-persona"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_persona(conn, redis_client, name="test-persona-visible")

    items = await get_personas(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-persona-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_persona(conn, redis_client, name="duplicate-persona")
    second = await create_persona(conn, redis_client, name="duplicate-persona")

    assert first.id != second.id
    assert second.name == "duplicate-persona"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_persona(conn, redis_client, name="mcp-persona", mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_creates_with_all_fields(conn, redis_client):
    from uuid import uuid4

    dept_id = uuid4()
    pf_id = uuid4()

    result = await create_persona(
        conn,
        redis_client,
        name="full-persona",
        description="full desc",
        icon="star",
        color="#FF0000",
        department_ids=[dept_id],
        instructions="Be helpful",
        examples=["Hello", "Goodbye"],
        parameter_field_ids=[pf_id],
    )

    assert result.name == "full-persona"
    assert result.description == "full desc"
    assert result.icon == "star"
    assert result.color == "#FF0000"
    assert result.department_ids == [dept_id]
    assert result.instructions == "Be helpful"
    assert result.examples == ["Hello", "Goodbye"]
    assert result.parameter_field_ids == [pf_id]


async def test_defaults_empty_for_optional_fields(conn, redis_client):
    result = await create_persona(conn, redis_client, name="minimal")

    assert result.icon == ""
    assert result.color == ""
    assert result.department_ids == []
    assert result.instructions == ""
    assert result.examples == []
    assert result.parameter_field_ids == []
