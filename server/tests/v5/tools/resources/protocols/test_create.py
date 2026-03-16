"""Tests for create_protocol."""

import pytest

from app.tools.resources.protocols.create import create_protocol
from app.tools.resources.protocols.get import get_protocols

pytestmark = pytest.mark.asyncio


async def test_creates_new_protocol(conn, redis_client):
    result = await create_protocol(conn, "https", redis_client)

    assert result.value == "https"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_protocol(conn, "http", redis_client)

    items = await get_protocols(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == "http"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_protocol(conn, "ftp", redis_client)
    second = await create_protocol(conn, "ftp", redis_client)

    assert first.id == second.id
    assert second.value == "ftp"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_protocol(conn, "ssh", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
