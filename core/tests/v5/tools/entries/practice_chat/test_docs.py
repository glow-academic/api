"""Tests for get_practice_chat_docs."""

import pytest

from app.tools.entries.practice_chat.docs import get_practice_chat_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_practice_chat_docs(conn)

    assert result.name == "practice_chat"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_practice_chat_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "practice_chat_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_practice_chat_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "practice_chat_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_practice_chat_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_practice_chat" in op_names
    assert "refresh_practice_chat" in op_names
    assert "get_practice_chats" in op_names
    assert "search_practice_chats" in op_names


async def test_create_operation_has_params(conn):
    result = await get_practice_chat_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_practice_chat"
    )
    param_names = [p.name for p in create_op.params]
    assert "practice_id" in param_names
    assert "chat_id" in param_names
    assert "session_id" in param_names
    assert "mcp" in param_names
