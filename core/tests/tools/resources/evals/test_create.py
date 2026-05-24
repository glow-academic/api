"""Tests for create_eval."""

import pytest

from app.tools.resources.evals.create import create_eval
from app.tools.resources.evals.get import get_evals

pytestmark = pytest.mark.asyncio


async def test_creates_new_eval(conn, redis_client):
    result = await create_eval(conn, redis_client, name="test-eval", description="desc")

    assert result.name == "test-eval"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_eval(conn, redis_client, name="test-eval-visible")

    items = await get_evals(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-eval-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_eval(conn, redis_client, name="duplicate-eval")
    second = await create_eval(conn, redis_client, name="duplicate-eval")

    assert first.id != second.id
    assert second.name == "duplicate-eval"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_eval(conn, redis_client, name="mcp-eval", mcp=True)

    assert result.mcp is True
    assert result.generated is True
