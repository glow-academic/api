"""Tests for create_rubric."""

import pytest

from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.rubrics.get import get_rubrics

pytestmark = pytest.mark.asyncio


async def test_creates_new_rubric(conn, redis_client):
    result = await create_rubric(
        conn, redis_client, name="test-rubric", description="desc"
    )

    assert result.name == "test-rubric"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_rubric(conn, redis_client, name="test-rubric-visible")

    items = await get_rubrics(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-rubric-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_rubric(conn, redis_client, name="duplicate-rubric")
    second = await create_rubric(conn, redis_client, name="duplicate-rubric")

    assert first.id != second.id
    assert second.name == "duplicate-rubric"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_rubric(conn, redis_client, name="mcp-rubric", mcp=True)

    assert result.mcp is True
    assert result.generated is True
