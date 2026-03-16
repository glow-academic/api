"""Tests for get_auth_docs."""

import pytest

from app.tools.artifacts.auth.docs import get_auth_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_auth_docs(conn)
    assert result.name == "auth"
    assert result.type == "artifact"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_auth_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "auth_artifact" in table_names


async def test_includes_all_operations(conn):
    result = await get_auth_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_auth" in op_names
    assert "update_auth" in op_names
    assert "get_auths" in op_names
    assert "search_auths" in op_names
    assert "delete_auths" in op_names


async def test_search_operation_has_params(conn):
    result = await get_auth_docs(conn)
    search_op = next(op for op in result.operations if op.name == "search_auths")
    param_names = [p.name for p in search_op.params]
    assert "search" in param_names
    assert "limit_count" in param_names
    assert "offset_count" in param_names
