"""Tests for get_run_pricing_docs."""

import pytest

from app.tools.entries.run_pricing.docs import get_run_pricing_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_run_pricing_docs(conn)

    assert result.name == "run_pricing"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_run_pricing_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "run_pricing_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_run_pricing_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "run_pricing_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_run_pricing_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_run_pricing_entry_internal" in op_names
    assert "refresh_run_pricing_internal" in op_names
    assert "get_run_pricing_entries_internal" in op_names
    assert "search_run_pricing_entries_internal" in op_names


async def test_create_operation_has_params(conn):
    result = await get_run_pricing_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_run_pricing_entry_internal"
    )
    param_names = [p.name for p in create_op.params]
    assert "session_id" in param_names
    assert "pricing_type" in param_names
    assert "run_id" in param_names
    assert "mcp" in param_names
