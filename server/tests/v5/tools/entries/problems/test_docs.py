"""Tests for get_problems_docs."""

import pytest

from app.tools.entries.problems.docs import get_problems_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_problems_docs(conn)

    assert result.name == "problems"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_problems_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "problems_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_problems_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "problems_entry" in table_names
    assert "profiles_problems_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_problems_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_problem" in op_names
    assert "refresh_problems" in op_names
    assert "get_problems" in op_names
    assert "search_problems" in op_names


async def test_search_operation_has_filters(conn):
    result = await get_problems_docs(conn)

    search_op = next(op for op in result.operations if op.name == "search_problems")
    param_names = [p.name for p in search_op.params]
    assert "profile_ids" in param_names
    assert "session_ids" in param_names
    assert "type" in param_names
    assert "resolved" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
