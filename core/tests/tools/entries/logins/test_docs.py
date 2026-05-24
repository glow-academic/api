"""Tests for get_logins_docs."""

import pytest

from app.tools.entries.logins.docs import get_logins_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_logins_docs(conn)

    assert result.name == "logins"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_logins_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "logins_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_logins_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "logins_entry" in table_names
    assert "profiles_logins_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_logins_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_login" in op_names
    assert "refresh_logins" in op_names
    assert "get_logins" in op_names
    assert "search_logins" in op_names


async def test_search_operation_has_filters(conn):
    result = await get_logins_docs(conn)

    search_op = next(op for op in result.operations if op.name == "search_logins")
    param_names = [p.name for p in search_op.params]
    assert "profile_ids" in param_names
    assert "session_ids" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
