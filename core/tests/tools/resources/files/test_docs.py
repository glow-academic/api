"""Tests for get_files_docs."""

import pytest

from app.tools.resources.files.docs import get_files_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_files_docs(conn)
    assert result.name == "files"
    assert result.type == "resource"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_files_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "files_resource" in table_names


async def test_includes_all_operations(conn):
    result = await get_files_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_file" in op_names
    assert "get_files" in op_names
    assert "search_files" in op_names


async def test_search_operation_has_params(conn):
    result = await get_files_docs(conn)
    search_op = next(op for op in result.operations if op.name == "search_files")
    param_names = [p.name for p in search_op.params]
    assert "limit_count" in param_names
    assert "offset_count" in param_names
