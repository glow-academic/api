"""Tests for get_sessions_docs."""

import pytest

from app.tools.entries.sessions.docs import get_sessions_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_sessions_docs(conn)

    assert result.name == "sessions"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_sessions_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "sessions_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_sessions_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "sessions_entry" in table_names
    assert "profiles_sessions_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_sessions_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_session" in op_names
    assert "refresh_sessions" in op_names
    assert "get_sessions" in op_names
    assert "search_sessions" in op_names


async def test_create_operation_has_params(conn):
    result = await get_sessions_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_session")
    param_names = [p.name for p in create_op.params]
    assert "profile_id" in param_names
    assert "mcp" in param_names


async def test_search_operation_has_filters(conn):
    result = await get_sessions_docs(conn)

    search_op = next(op for op in result.operations if op.name == "search_sessions")
    param_names = [p.name for p in search_op.params]
    assert "profile_ids" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "active" in param_names
    assert "mcp" in param_names


async def test_operations_have_return_types(conn):
    result = await get_sessions_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_session")
    assert create_op.returns is not None
    assert "CreateSessionResponse" in create_op.returns["type"]

    get_op = next(op for op in result.operations if op.name == "get_sessions")
    assert get_op.returns is not None
    assert "GetSessionResponse" in get_op.returns["type"]
