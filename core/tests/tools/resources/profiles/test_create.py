"""Tests for create_profile."""

import pytest

from app.tools.resources.profiles.create import create_profile
from app.tools.resources.profiles.get import get_profiles

pytestmark = pytest.mark.asyncio


async def test_creates_new_profile(conn, redis_client):
    result = await create_profile(
        conn, redis_client, name="test-profile", description="Test desc"
    )

    assert result.name == "test-profile"
    assert result.description == "Test desc"
    assert result.active is True
    assert result.mcp is False
    assert result.department_ids == []
    assert result.emails == []


async def test_visible_via_get(conn, redis_client):
    result = await create_profile(conn, redis_client, name="visible-profile")

    items = await get_profiles(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "visible-profile"


async def test_creates_second_row_for_same_params(conn, redis_client):
    first = await create_profile(conn, redis_client, name="dup-profile")
    second = await create_profile(conn, redis_client, name="dup-profile")

    assert first.id != second.id
    assert second.name == "dup-profile"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_profile(conn, redis_client, name="mcp-profile", mcp=True)

    assert result.mcp is True
    assert result.generated is True
