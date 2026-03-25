"""Tests for create_cohort."""

import pytest

from app.tools.resources.cohorts.create import create_cohort
from app.tools.resources.cohorts.get import get_cohorts

pytestmark = pytest.mark.asyncio


async def test_creates_new_cohort(conn, redis_client):
    result = await create_cohort(
        conn, redis_client, name="test-cohort", description="desc"
    )

    assert result.name == "test-cohort"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_cohort(conn, redis_client, name="test-cohort-visible")

    items = await get_cohorts(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-cohort-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_cohort(conn, redis_client, name="duplicate-cohort")
    second = await create_cohort(conn, redis_client, name="duplicate-cohort")

    assert first.id != second.id
    assert second.name == "duplicate-cohort"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_cohort(conn, redis_client, name="mcp-cohort", mcp=True)

    assert result.mcp is True
    assert result.generated is True
