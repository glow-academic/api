"""Tests for create_question."""

import pytest

from app.tools.resources.questions.create import create_question
from app.tools.resources.questions.get import get_questions

pytestmark = pytest.mark.asyncio


async def test_creates_new_question(conn, redis_client):
    result = await create_question(conn, "What is the capital?", 30, redis_client)

    assert result.question_text == "What is the capital?"
    assert result.time == 30
    assert result.allow_multiple is False
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_question(conn, "How many continents?", 60, redis_client)

    items = await get_questions(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_question(conn, "Duplicate question?", 30, redis_client)
    second = await create_question(conn, "Duplicate question?", 30, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_question(conn, "MCP question?", 30, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
