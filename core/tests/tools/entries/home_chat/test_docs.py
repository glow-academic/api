"""Tests for get_home_chat_docs."""

import pytest

from app.tools.entries.home_chat.docs import get_home_chat_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_home_chat_docs(conn)

    assert result.name == "home_chat"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_home_chat_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "home_chat_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_home_chat_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "home_chat_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_home_chat_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_home_chat" in op_names
    assert "get_home_chats" in op_names
    assert "search_home_chats" in op_names


async def test_create_operation_has_params(conn):
    result = await get_home_chat_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_home_chat")
    param_names = [p.name for p in create_op.params]
    assert len(param_names) > 0
