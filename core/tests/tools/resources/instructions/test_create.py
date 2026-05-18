"""Tests for create_instruction."""

import pytest

from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.instructions.get import get_instructions

pytestmark = pytest.mark.asyncio


async def test_creates_new_instruction(conn, redis_client):
    result = await create_instruction(conn, "test-template", redis_client)

    assert result.template == "test-template"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_instruction(conn, "test-template-visible", redis_client)

    items = await get_instructions(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].template == "test-template-visible"


async def test_creates_second_row(conn, redis_client):
    first = await create_instruction(conn, "duplicate-template", redis_client)
    second = await create_instruction(conn, "duplicate-template", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_instruction(conn, "mcp-template", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
