"""Tests for create_option."""

import pytest

from app.tools.resources.options.create import create_option
from app.tools.resources.options.get import get_options

pytestmark = pytest.mark.asyncio


async def test_creates_new_option(conn, redis_client):
    result = await create_option(conn, "option A", redis_client)

    assert result.option_text == "option A"
    assert result.is_correct is False
    assert result.question_id is None
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_option(conn, "option B", redis_client)

    items = await get_options(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].option_text == "option B"


async def test_creates_second_row_for_same_text(conn, redis_client):
    first = await create_option(conn, "duplicate option", redis_client)
    second = await create_option(conn, "duplicate option", redis_client)

    assert first.id != second.id
    assert second.option_text == "duplicate option"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_option(conn, "mcp option", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
