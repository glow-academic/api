"""Tests for get_qualities_docs."""

import pytest

from app.tools.resources.qualities.docs import get_qualities_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_qualities_docs(conn)
    assert result.name == "qualities"
    assert result.type == "resource"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_qualities_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "qualities_resource" in table_names


async def test_includes_all_operations(conn):
    result = await get_qualities_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_quality" in op_names
    assert "get_qualities" in op_names
    assert "search_qualities" in op_names


async def test_search_operation_has_params(conn):
    result = await get_qualities_docs(conn)
    search_op = next(op for op in result.operations if op.name == "search_qualities")
    param_names = [p.name for p in search_op.params]
    assert "limit_count" in param_names
    assert "offset_count" in param_names
