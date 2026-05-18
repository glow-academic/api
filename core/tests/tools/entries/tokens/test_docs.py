"""Tests for get_tokens_docs."""

import pytest

from app.tools.entries.tokens.docs import get_tokens_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs(conn):
    result = await get_tokens_docs(conn)

    assert result.name == "tokens"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_mv(conn):
    result = await get_tokens_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "tokens_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_tables(conn):
    result = await get_tokens_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "tokens_entry" in table_names


async def test_includes_operations(conn):
    result = await get_tokens_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_token" in op_names
    assert "refresh_tokens" in op_names
    assert "get_tokens" in op_names
    assert "search_tokens" in op_names


async def test_search_has_filters(conn):
    result = await get_tokens_docs(conn)

    search_op = next(op for op in result.operations if op.name == "search_tokens")
    param_names = [p.name for p in search_op.params]
    assert "run_ids" in param_names
    assert "session_ids" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
