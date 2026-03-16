"""Tests for get_attempt_chat_completion_docs."""

import pytest

from app.tools.entries.attempt_chat_completion.docs import (
    get_attempt_chat_completion_docs,
)

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_attempt_chat_completion_docs(conn)

    assert result.name == "attempt_chat_completion"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_attempt_chat_completion_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "attempt_chat_completion_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_attempt_chat_completion_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "attempt_chat_completion_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_attempt_chat_completion_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_attempt_chat_completion" in op_names
    assert "refresh_attempt_chat_completion" in op_names
    assert "get_attempt_chat_completions" in op_names
    assert "search_attempt_chat_completions" in op_names


async def test_create_operation_has_params(conn):
    result = await get_attempt_chat_completion_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_attempt_chat_completion"
    )
    param_names = [p.name for p in create_op.params]
    assert "chat_id" in param_names
    assert "call_id" in param_names
    assert "stop" in param_names
    assert "error" in param_names
    assert "message" in param_names
