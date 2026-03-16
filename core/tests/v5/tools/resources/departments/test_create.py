"""Tests for create_department."""

import pytest

from app.tools.resources.departments.create import create_department
from app.tools.resources.departments.get import get_departments
from app.tools.resources.settings.create import create_setting

pytestmark = pytest.mark.asyncio


async def test_creates_new_department(conn, redis_client):
    result = await create_department(conn, "test-dept", "desc", redis_client)

    assert result.name == "test-dept"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_department(conn, "test-dept-visible", redis=redis_client)

    items = await get_departments(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-dept-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_department(conn, "test-dept-dup", redis=redis_client)
    second = await create_department(conn, "test-dept-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_department(conn, "mcp-dept", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_round_trips_setting_links_and_primary_flag(conn, redis_client):
    setting = await create_setting(conn, "dept-setting", redis=redis_client)

    result = await create_department(
        conn,
        "linked-dept",
        redis=redis_client,
        setting_ids=[setting.id],
        is_primary=True,
    )

    items = await get_departments(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].setting_ids == [setting.id]
    assert items[0].is_primary is True
