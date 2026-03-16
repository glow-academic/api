"""Tests for get_invocation_docs."""

import pytest

from app.tools.entries.invocation.docs import get_invocation_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_invocation_docs(conn)

    assert result.name == "invocation"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_no_materialized_view(conn):
    result = await get_invocation_docs(conn)

    assert result.materialized_view is None


async def test_includes_source_tables(conn):
    result = await get_invocation_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "invocation_entry" in table_names
    assert "invocation_departments_connection" in table_names
    assert "invocation_models_connection" in table_names
    assert "invocation_names_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_invocation_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_invocation" in op_names
    assert "get_invocations" in op_names


async def test_create_operation_has_params(conn):
    result = await get_invocation_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_invocation")
    param_names = [p.name for p in create_op.params]
    assert "benchmark_id" in param_names
