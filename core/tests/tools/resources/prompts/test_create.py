"""Tests for create_prompt."""

import pytest

from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.prompts.get import get_prompts

pytestmark = pytest.mark.asyncio


async def test_creates_new_prompt(conn, redis_client):
    result = await create_prompt(
        conn, "You are an assistant.", "test-prompt", "A test prompt.", redis_client
    )

    assert result.system_prompt == "You are an assistant."
    assert result.name == "test-prompt"
    assert result.description == "A test prompt."
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_prompt(
        conn, "Visible system prompt.", "visible-prompt", "Visible desc.", redis_client
    )

    items = await get_prompts(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "visible-prompt"


async def test_creates_second_row(conn, redis_client):
    first = await create_prompt(
        conn,
        "Duplicate system prompt.",
        "duplicate-prompt",
        "Duplicate desc.",
        redis_client,
    )
    second = await create_prompt(
        conn,
        "Duplicate system prompt.",
        "duplicate-prompt",
        "Duplicate desc.",
        redis_client,
    )

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_prompt(
        conn, "MCP system prompt.", "mcp-prompt", "MCP desc.", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
