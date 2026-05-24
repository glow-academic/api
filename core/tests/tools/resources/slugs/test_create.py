"""Tests for create_slug."""

import pytest

from app.tools.resources.slugs.create import create_slug
from app.tools.resources.slugs.get import get_slugs

pytestmark = pytest.mark.asyncio


async def test_creates_new_slug(conn, redis_client):
    result = await create_slug(conn, "my-new-slug", redis_client)

    assert result.value == "my-new-slug"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_slug(conn, "visible-slug", redis_client)

    items = await get_slugs(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].value == "visible-slug"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_slug(conn, "duplicate-slug", redis_client)
    second = await create_slug(conn, "duplicate-slug", redis_client)

    assert first.id == second.id
    assert second.value == "duplicate-slug"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_slug(conn, "mcp-slug", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
