"""Tests for get_temperature_levels_docs."""

import pytest

from app.tools.resources.temperature_levels.docs import (
    get_temperature_levels_docs,
)

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_temperature_levels_docs(conn)
    assert result.name == "temperature_levels"
    assert result.type == "resource"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_temperature_levels_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "temperature_levels_resource" in table_names


async def test_includes_all_operations(conn):
    result = await get_temperature_levels_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_temperature_level" in op_names
    assert "get_temperature_levels" in op_names
    assert "search_temperature_levels" in op_names


async def test_search_operation_has_params(conn):
    result = await get_temperature_levels_docs(conn)
    search_op = next(
        op for op in result.operations if op.name == "search_temperature_levels"
    )
    param_names = [p.name for p in search_op.params]
    assert "limit_count" in param_names
    assert "offset_count" in param_names
