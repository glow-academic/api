"""Tests for create_file."""

import pytest

from app.tools.resources.files.create import create_file
from app.tools.resources.files.get import get_files

pytestmark = pytest.mark.asyncio


async def test_creates_new_file(conn, redis_client):
    result = await create_file(conn, redis_client)

    assert result.id is not None
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_file(conn, redis_client)

    items = await get_files(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_file(conn, redis_client)
    second = await create_file(conn, redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_file(conn, redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
