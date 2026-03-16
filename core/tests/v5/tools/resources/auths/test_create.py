"""Tests for create_auth."""

import pytest

from app.tools.resources.auths.create import create_auth
from app.tools.resources.auths.get import get_auths

pytestmark = pytest.mark.asyncio


async def test_creates_new_auth(conn, redis_client):
    result = await create_auth(conn, redis_client, name="test-auth")

    assert result.name == "test-auth"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_auth(conn, redis_client, name="test-auth-visible")

    items = await get_auths(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-auth-visible"


async def test_no_conflict_creates_different_rows(conn, redis_client):
    first = await create_auth(conn, redis_client, name="duplicate-auth")
    second = await create_auth(conn, redis_client, name="duplicate-auth")

    assert first.id != second.id
    assert second.name == "duplicate-auth"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_auth(conn, redis_client, name="mcp-auth", mcp=True)

    assert result.mcp is True
    assert result.generated is True
