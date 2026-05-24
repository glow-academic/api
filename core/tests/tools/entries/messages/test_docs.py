"""Tests for get_messages_docs."""

import pytest

from app.tools.entries.messages.docs import get_messages_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_messages_docs(conn)

    assert result.name == "messages"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_no_materialized_view(conn):
    result = await get_messages_docs(conn)

    assert result.materialized_view is None


async def test_includes_source_tables(conn):
    result = await get_messages_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "messages_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_messages_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_message" in op_names
    assert "get_message" in op_names
    assert "search_messages" in op_names


async def test_create_operation_has_params(conn):
    result = await get_messages_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_message")
    param_names = [p.name for p in create_op.params]
    assert "run_id" in param_names or "session_id" in param_names
