"""Tests for get_benchmark_docs."""

import pytest

from app.tools.entries.benchmark.docs import get_benchmark_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_benchmark_docs(conn)

    assert result.name == "benchmark"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_benchmark_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "benchmark_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_benchmark_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "benchmark_entry" in table_names
    assert "benchmark_evals_connection" in table_names
    assert "benchmark_profiles_connection" in table_names
    assert "benchmark_departments_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_benchmark_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_benchmark" in op_names
    assert "get_benchmarks" in op_names
    assert "search_benchmarks" in op_names


async def test_create_operation_has_params(conn):
    result = await get_benchmark_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_benchmark")
    param_names = [p.name for p in create_op.params]
    assert "session_id" in param_names
    assert "mcp" in param_names
