"""Tests for get_persona_docs."""

import pytest

from app.tools.artifacts.persona.docs import get_persona_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_persona_docs(conn)
    assert result.name == "persona"
    assert result.type == "artifact"
    assert len(result.description) > 0


async def test_includes_source_tables(conn):
    result = await get_persona_docs(conn)
    table_names = [t.name for t in result.tables]
    assert "persona_artifact" in table_names


async def test_includes_all_operations(conn):
    result = await get_persona_docs(conn)
    op_names = [op.name for op in result.operations]
    assert "create_persona" in op_names
    assert "update_persona" in op_names
    assert "get_personas" in op_names
    assert "search_personas" in op_names
    assert "delete_personas" in op_names


async def test_search_operation_has_params(conn):
    result = await get_persona_docs(conn)
    search_op = next(op for op in result.operations if op.name == "search_personas")
    param_names = [p.name for p in search_op.params]
    assert "search" in param_names
    assert "limit_count" in param_names
    assert "offset_count" in param_names
