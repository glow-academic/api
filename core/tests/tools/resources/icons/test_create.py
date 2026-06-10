"""Tests for create_icon."""

import pytest

from app.tools.resources.icons.create import create_icon
from app.tools.resources.icons.get import get_icons

pytestmark = pytest.mark.asyncio


async def test_creates_new_icon(conn, redis_client):
    result = await create_icon(conn, "test-icon", "An icon", "home", redis_client)

    assert result.name == "test-icon"
    assert result.description == "An icon"
    assert result.value == "home"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_icon(conn, "test-icon-visible", "desc", "bell", redis_client)

    items = await get_icons(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_icon(conn, "duplicate-icon", "desc", "flag", redis_client)
    second = await create_icon(conn, "duplicate-icon", "desc", "flag", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_icon(
        conn, "mcp-icon", "desc", "robot", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True


async def test_stores_sanitized_value_for_malicious_svg(conn, redis_client):
    """A malicious icon value is sanitized before it reaches the DB."""
    result = await create_icon(
        conn,
        "xss-icon",
        "desc",
        '<svg onload="alert(1)"><script>alert(2)</script><path d="M0 0z"/></svg>',
        redis_client,
    )

    assert "onload" not in result.value
    assert "<script" not in result.value
    assert "alert" not in result.value
    assert result.value.startswith("<svg")
    assert "<path" in result.value


async def test_stores_valid_svg_intact(conn, redis_client):
    valid = '<svg viewBox="0 0 24 24"><path d="M0 0z"/></svg>'
    result = await create_icon(conn, "valid-svg-icon", "desc", valid, redis_client)

    assert result.value.startswith("<svg")
    assert "<path" in result.value


async def test_stores_plain_name_intact(conn, redis_client):
    result = await create_icon(conn, "name-icon", "desc", "robot", redis_client)

    assert result.value == "robot"
