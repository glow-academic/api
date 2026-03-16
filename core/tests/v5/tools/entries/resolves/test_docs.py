"""Tests for get_resolves_docs."""

import pytest

from app.tools.entries.resolves.docs import get_resolves_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs(conn):
    result = await get_resolves_docs(conn)

    assert result.name == "resolves"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_mv(conn):
    result = await get_resolves_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "resolves_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_tables(conn):
    result = await get_resolves_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "resolves_entry" in table_names


async def test_includes_operations(conn):
    result = await get_resolves_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_resolve" in op_names
    assert "refresh_resolves" in op_names
    assert "get_resolves" in op_names
    assert "search_resolves" in op_names


async def test_search_has_filters(conn):
    result = await get_resolves_docs(conn)

    search_op = next(op for op in result.operations if op.name == "search_resolves")
    param_names = [p.name for p in search_op.params]
    assert "problem_ids" in param_names
    assert "call_ids" in param_names
    assert "resolved" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
