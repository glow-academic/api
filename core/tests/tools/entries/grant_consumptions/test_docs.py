"""Tests for get_grant_consumptions_docs."""

import pytest

from app.tools.entries.grant_consumptions.docs import (
    get_grant_consumptions_docs,
)

pytestmark = pytest.mark.asyncio


async def test_returns_docs(conn):
    result = await get_grant_consumptions_docs(conn)

    assert result.name == "grant_consumptions"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_no_mv(conn):
    result = await get_grant_consumptions_docs(conn)

    assert result.materialized_view is None


async def test_includes_tables(conn):
    result = await get_grant_consumptions_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "grant_consumptions_entry" in table_names


async def test_includes_operations(conn):
    result = await get_grant_consumptions_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_grant_consumption" in op_names
    assert "get_grant_consumptions" in op_names
    assert "search_grant_consumptions" in op_names


async def test_search_has_filters(conn):
    result = await get_grant_consumptions_docs(conn)

    search_op = next(
        op for op in result.operations if op.name == "search_grant_consumptions"
    )
    param_names = [p.name for p in search_op.params]
    assert "grant_ids" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
