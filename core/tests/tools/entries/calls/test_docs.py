"""Tests for get_calls_docs."""

import pytest

from app.tools.entries.calls.docs import get_calls_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_calls_docs(conn)

    assert result.name == "calls"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_calls_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "calls_entry" in table_names
    assert "tools_calls_connection" in table_names


async def test_no_materialized_view(conn):
    result = await get_calls_docs(conn)

    assert result.materialized_view is None


async def test_includes_all_operations(conn):
    result = await get_calls_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_call" in op_names
    assert "get_call" in op_names
    assert "search_calls" in op_names


async def test_create_operation_has_params(conn):
    result = await get_calls_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_call")
    param_names = [p.name for p in create_op.params]
    assert "run_id" in param_names or "session_id" in param_names
