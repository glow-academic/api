"""Tests for create_problem_statement."""

import pytest

from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.problem_statements.get import get_problem_statements

pytestmark = pytest.mark.asyncio


async def test_creates_new_problem_statement(conn, redis_client):
    result = await create_problem_statement(
        conn, "test-name", "test problem statement", redis_client
    )

    assert result.name == "test-name"
    assert result.problem_statement == "test problem statement"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_problem_statement(
        conn, "visible-name", "visible problem statement", redis_client
    )

    items = await get_problem_statements(
        conn, [result.id], redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "visible-name"


async def test_creates_second_row(conn, redis_client):
    first = await create_problem_statement(
        conn, "duplicate-name", "duplicate problem statement", redis_client
    )
    second = await create_problem_statement(
        conn, "duplicate-name", "duplicate problem statement", redis_client
    )

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_problem_statement(
        conn, "mcp-name", "mcp problem statement", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
