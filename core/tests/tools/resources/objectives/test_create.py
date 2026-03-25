"""Tests for create_objective."""

import pytest

from app.tools.resources.objectives.create import create_objective
from app.tools.resources.objectives.get import get_objectives

pytestmark = pytest.mark.asyncio


async def test_creates_new_objective(conn, redis_client):
    result = await create_objective(conn, "test-objective", redis_client)

    assert result.objective == "test-objective"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_objective(conn, "test-objective-visible", redis_client)

    items = await get_objectives(conn, [result.id], redis_client, bypass_cache=True)
    assert len(items) == 1
    assert items[0].id == result.id


async def test_creates_second_row(conn, redis_client):
    first = await create_objective(conn, "duplicate-objective", redis_client)
    second = await create_objective(conn, "duplicate-objective", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_objective(conn, "mcp-objective", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
