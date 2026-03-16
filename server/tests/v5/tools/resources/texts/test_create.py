"""Tests for create_text."""

import pytest

from app.tools.resources.texts.create import create_text
from app.tools.resources.texts.get import get_texts

pytestmark = pytest.mark.asyncio


async def test_creates_new_text(conn, redis_client):
    result = await create_text(conn, redis_client)

    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_text(conn, redis_client)

    items = await get_texts(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_text(conn, redis_client)
    second = await create_text(conn, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_text(conn, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
