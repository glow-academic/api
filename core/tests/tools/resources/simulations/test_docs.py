"""Tests for get_simulations_docs."""

import pytest

from app.tools.resources.simulations.docs import get_simulations_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_simulations_docs(conn)
    assert result.name == "simulations"
    assert result.type == "resource"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_simulations_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "simulations_resource" in table_names


async def test_includes_all_operations(conn):
    result = await get_simulations_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_simulation" in op_names
    assert "get_simulations" in op_names
    assert "search_simulations" in op_names


async def test_search_operation_has_params(conn):
    result = await get_simulations_docs(conn)
    search_op = next(op for op in result.operations if op.name == "search_simulations")
    param_names = [p.name for p in search_op.params]
    assert "limit_count" in param_names
    assert "offset_count" in param_names
