"""Tests for get_metrics_docs."""

import pytest

from app.tools.entries.metrics.docs import get_metrics_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_metrics_docs(conn)

    assert result.name == "metrics"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_has_materialized_view(conn):
    result = await get_metrics_docs(conn)

    assert result.materialized_view is not None


async def test_includes_source_tables(conn):
    result = await get_metrics_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "metrics_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_metrics_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_metrics_entry_internal" in op_names
    assert "get_metrics" in op_names
    assert "search_metrics" in op_names


async def test_create_operation_has_params(conn):
    result = await get_metrics_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_metrics_entry_internal"
    )
    param_names = [p.name for p in create_op.params]
    assert len(param_names) > 0
